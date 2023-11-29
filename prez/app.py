import logging
import os
from textwrap import dedent

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from rdflib import Graph
from starlette.middleware.cors import CORSMiddleware

from prez.config import settings
from prez.dependencies import (
    get_async_http_client,
    get_pyoxi_store,
    load_local_data_to_oxigraph,
    get_oxrdflib_store,
    get_system_store,
    load_profile_data_to_oxigraph,
)
from prez.models.model_exceptions import (
    ClassNotFoundException,
    URINotFoundException,
    NoProfilesException,
)
from prez.routers.catprez import router as catprez_router
from prez.routers.cql import router as cql_router
from prez.routers.identifier import router as identifier_router
from prez.routers.management import router as management_router
from prez.routers.object import router as object_router
from prez.routers.profiles import router as profiles_router
from prez.routers.search import router as search_router
from prez.routers.spaceprez import router as spaceprez_router
from prez.routers.sparql import router as sparql_router
from prez.routers.vocprez import router as vocprez_router
from prez.services.app_service import (
    healthcheck_sparql_endpoints,
    count_objects,
    create_endpoints_graph,
    populate_api_info,
    add_prefixes_to_prefix_graph,
    add_common_context_ontologies_to_tbox_cache,
)
from prez.services.exception_catchers import (
    catch_400,
    catch_404,
    catch_500,
    catch_class_not_found_exception,
    catch_uri_not_found_exception,
    catch_no_profiles_exception,
)
from prez.services.generate_profiles import create_profiles_graph
from prez.services.prez_logging import setup_logger
from prez.services.search_methods import get_all_search_methods
from prez.sparql.methods import RemoteSparqlRepo, PyoxigraphRepo, OxrdflibRepo

app = FastAPI(
    exception_handlers={
        400: catch_400,
        404: catch_404,
        500: catch_500,
        ClassNotFoundException: catch_class_not_found_exception,
        URINotFoundException: catch_uri_not_found_exception,
        NoProfilesException: catch_no_profiles_exception,
    }
)


app.include_router(cql_router)
app.include_router(management_router)
app.include_router(object_router)
app.include_router(sparql_router)
app.include_router(search_router)
app.include_router(profiles_router)
if "CatPrez" in settings.prez_flavours:
    app.include_router(catprez_router)
if "VocPrez" in settings.prez_flavours:
    app.include_router(vocprez_router)
if "SpacePrez" in settings.prez_flavours:
    app.include_router(spaceprez_router)
app.include_router(identifier_router)


@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


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

    if settings.sparql_repo_type == "pyoxigraph":
        app.state.pyoxi_store = get_pyoxi_store()
        app.state.repo = PyoxigraphRepo(app.state.pyoxi_store)
        await load_local_data_to_oxigraph(app.state.pyoxi_store)
    elif settings.sparql_repo_type == "oxrdflib":
        app.state.oxrdflib_store = get_oxrdflib_store()
        app.state.repo = OxrdflibRepo(app.state.oxrdflib_store)
    elif settings.sparql_repo_type == "remote":
        app.state.http_async_client = await get_async_http_client()
        app.state.repo = RemoteSparqlRepo(app.state.http_async_client)
        await healthcheck_sparql_endpoints()
    else:
        raise ValueError(
            "SPARQL_REPO_TYPE must be one of 'pyoxigraph', 'oxrdflib' or 'remote'"
        )

    await add_prefixes_to_prefix_graph(app.state.repo)
    await get_all_search_methods(app.state.repo)
    await create_profiles_graph(app.state.repo)
    await create_endpoints_graph(app.state.repo)
    await count_objects(app.state.repo)
    await populate_api_info()
    await add_common_context_ontologies_to_tbox_cache()

    app.state.pyoxi_system_store = get_system_store()
    await load_profile_data_to_oxigraph(app.state.pyoxi_system_store)


@app.on_event("shutdown")
async def app_shutdown():
    """
    persists caches
    close async SPARQL clients
    """
    log = logging.getLogger("prez")
    log.info("Shutting down...")

    # close all SPARQL async clients
    if not settings.sparql_repo_type:
        await app.state.http_async_client.aclose()


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
