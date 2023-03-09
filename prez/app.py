import logging
import os
from textwrap import dedent

import uvicorn
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from rdflib import Graph, Literal, URIRef
from starlette.middleware.cors import CORSMiddleware

from prez.cache import tbox_cache
from prez.config import settings
from prez.services.app_service import (
    populate_api_info,
    generate_support_graphs,
    generate_profiles_support_graph,
)
from prez.renderers.renderer import return_rdf
from prez.routers.catprez import router as catprez_router
from prez.routers.cql import router as cql_router
from prez.routers.management import router as management_router
from prez.routers.object import router as object_router
from prez.routers.profiles import router as profiles_router
from prez.routers.spaceprez import router as spaceprez_router
from prez.routers.search import router as search_router
from prez.routers.sparql import router as sparql_router
from prez.routers.vocprez import router as vocprez_router
from prez.services.app_service import healthcheck_sparql_endpoints, count_objects
from prez.services.generate_profiles import create_profiles_graph
from prez.services.prez_logging import setup_logger
from prez.reference_data.prez_ns import PREZ
from prez.services.search_methods import generate_search_methods


async def catch_400(request: Request, exc):
    return JSONResponse(content={"detail": exc}, status_code=400)


async def catch_404(request: Request, exc):
    return JSONResponse(content={"detail": str(exc.detail)}, status_code=404)


async def catch_500(request: Request, exc):
    return JSONResponse(content={"detail": "Internal Server Error"}, status_code=500)


app = FastAPI(
    exception_handlers={
        400: catch_400,
        404: catch_404,
        500: catch_500,
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(cql_router)
app.include_router(management_router)
app.include_router(object_router)
app.include_router(sparql_router)
app.include_router(search_router)
app.include_router(profiles_router)
if settings.catprez_sparql_endpoint:
    app.include_router(catprez_router)
if settings.vocprez_sparql_endpoint:
    app.include_router(vocprez_router)
if settings.spaceprez_sparql_endpoint:
    app.include_router(spaceprez_router)


def prez_open_api_metadata():
    return get_openapi(
        title=settings.prez_title,
        version=settings.prez_version,
        description=settings.prez_desc,
        routes=app.routes,
    )


app.openapi = prez_open_api_metadata


@app.on_event("startup")
async def app_startup():
    """
    This function runs at startup and will continually poll the separate backends until their SPARQL endpoints
    are available. Initial caching can be triggered within the try block. NB this function does not check that data is
    appropriately configured at the SPARQL endpoint(s), only that the SPARQL endpoint(s) are reachable.
    """
    setup_logger(settings)
    log = logging.getLogger("prez")
    log.info("Starting up")
    await healthcheck_sparql_endpoints()
    await generate_search_methods()
    await create_profiles_graph()
    await count_objects()
    await generate_profiles_support_graph()
    await populate_api_info()
    await generate_support_graphs()


@app.on_event("shutdown")
async def app_shutdown():
    """
    persists caches
    close async SPARQL clients
    """
    log = logging.getLogger("prez")
    log.info("Shutting down...")
    if len(tbox_cache) > 0:
        tbox_cache.serialize(destination="tbox_cache.nt", format="nt")
    # close all SPARQL async clients
    if not os.getenv("TEST_MODE") == "true":
        from prez.services.triplestore_client import sparql_clients

        for k, v in sparql_clients.items():
            await v.aclose()


@app.get("/", summary="Home page", tags=["Prez"])
async def index(request: Request):
    """Returns the following information about the API"""
    # TODO connegp on request. don't need profiles for this
    from prez.cache import (
        prez_system_graph,
        tbox_cache,
    )  # importing at module level will get the empty graph before it's populated

    prez_system_graph.add(
        (
            URIRef(settings.system_uri),
            PREZ.currentTBOXCacheSize,
            Literal(len(tbox_cache)),
        )
    )
    return await return_rdf(
        prez_system_graph, mediatype="text/anot+turtle", profile_headers={}
    )


def _get_sparql_service_description(request, format):
    """Return an RDF description of PROMS' read only SPARQL endpoint in a requested format
    :param rdf_fmt: 'turtle', 'n3', 'xml', 'json-ld'
    :return: string of RDF in the requested format
    """
    ttl = """
        @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix sd:     <http://www.w3.org/ns/sparql-service-description#> .
        @prefix sdf:    <http://www.w3.org/ns/formats/> .
        @prefix void:   <http://rdfs.org/ns/void#> .
        @prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
        <{0}>
            a                       sd:Service ;
            sd:endpoint             <{0}> ;
            sd:supportedLanguage    sd:SPARQL11Query ; # yes, read only, sorry!
            sd:resultFormat         sdf:SPARQL_Results_JSON ;  # yes, we only deliver JSON results, sorry!
            sd:feature sd:DereferencesURIs ;
            sd:defaultDataset [
                a sd:Dataset ;
                sd:defaultGraph [
                    a sd:Graph ;
                    void:triples "100"^^xsd:integer
                ]
            ]
        .
    """.format(
        request.url_for("sparql_get")
    )
    if format == "text/turtle":
        return dedent(ttl)
    else:
        return Graph(bind_namespaces="rdflib").parse(data=ttl).serialize(format=format)


if __name__ == "__main__":
    uvicorn.run("app:app", port=settings.port, host=settings.host)
