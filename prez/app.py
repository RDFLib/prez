from textwrap import dedent
from typing import Optional, List
from urllib.parse import quote_plus

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fedsearch import SkosSearch, EndpointDetails
from pydantic import AnyUrl
from starlette.middleware.cors import CORSMiddleware

from prez.models.api_model import populate_api_info
from prez.cache import tbox_cache, api_info_graph
from prez.config import Settings
from prez.profiles.generate_profiles import create_profiles_graph
from prez.routers.catprez import router as catprez_router
from prez.routers.cql import router as cql_router
from prez.routers.spaceprez import router as spaceprez_router
from prez.routers.vocprez import router as vocprez_router
from prez.services.app_service import *
from prez.services.spaceprez_service import list_datasets, list_collections
from prez.renderers.renderer import return_rdf


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
settings = Settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(cql_router)
if settings.catprez_sparql_endpoint:
    app.include_router(catprez_router)
if settings.vocprez_sparql_endpoint:
    app.include_router(vocprez_router)
if settings.spaceprez_sparql_endpoint:
    app.include_router(spaceprez_router)


@app.on_event("startup")
async def app_startup():
    """
    This function runs at startup and will continually poll the separate backends until their SPARQL endpoints
    are available. Initial caching can be triggered within the try block. NB this function does not check that data is
    appropriately configured at the SPARQL endpoint(s), only that the SPARQL endpoint(s) are reachable.
    """
    print("Starting up...")
    await healthcheck_sparql_endpoints(settings)
    create_profiles_graph(settings.enabled_prezs)
    await count_objects(settings)
    populate_api_info(settings.enabled_prezs, settings.system_uri)


@app.on_event("shutdown")
async def app_shutdown():
    """
    persists caches
    """
    print("Shutting down...")
    if len(tbox_cache) > 0:
        tbox_cache.serialize(destination="tbox_cache.nt", format="nt")


@app.get("/", summary="Home page")
async def index(request: Request):
    """Returns the following information about the API"""
    # TODO connegp on request. don't need profiles for this
    return await return_rdf(api_info_graph, mediatype="text/turtle")


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
        return Graph().parse(data=ttl).serialize(format=format)


# TODO DRY fix 3x SPARQL endpoints below
@app.get("/s/sparql", summary="SpacePrez SPARQL Endpoint")
async def sparql_get(request: Request, query: Optional[str] = None):
    if not request.query_params:
        raise ValueError("A SPARQL query must be provided as a query parameter")
    return RedirectResponse(
        url=settings.SPACEPREZ_SPARQL_ENDPOINT + "?" + str(request.query_params)
    )


@app.get("/v/sparql", summary="VocPrez SPARQL Endpoint")
async def sparql_get(request: Request, query: Optional[str] = None):
    if not request.query_params:
        raise ValueError("A SPARQL query must be provided as a query parameter")
    return RedirectResponse(
        url=settings.VOCPREZ_SPARQL_ENDPOINT + "?" + str(request.query_params)
    )


@app.get("/c/sparql", summary="CatPrez SPARQL Endpoint")
async def sparql_get(request: Request, query: Optional[str] = None):
    if not request.query_params:
        raise ValueError("A SPARQL query must be provided as a query parameter")
    return RedirectResponse(
        url=settings.CATPREZ_SPARQL_ENDPOINT + "?" + str(request.query_params)
    )


@app.get("/search", summary="Search page")
async def search(
    request: Request,
    search: Optional[str] = None,
    endpoints: List[str] = Query(["self"]),
):
    """Displays the search page of Prez"""
    # Concept search
    if search is not None and search != "":
        self_sparql_endpoint = str(request.base_url)[:-1] + "/sparql"
        endpoint_details = []
        for endpoint in endpoints:
            if endpoint in [
                e["url"] for e in SEARCH_ENDPOINTS
            ]:  # only use valid endpoints
                if endpoint == "self":
                    endpoint_details.append(
                        EndpointDetails(self_sparql_endpoint, None, None)
                    )
                else:
                    endpoint_details.append(EndpointDetails(endpoint, None, None))
        s = []
        retries = 0
        while retries < 3:
            try:
                s = await SkosSearch.federated_search(
                    search, "preflabel", endpoint_details
                )
                break
            except Exception:
                retries += 1
                continue
        if retries == 3:
            raise Exception("Max retries reached")
        results = SkosSearch.combine_search_results(s, "preflabel")
    else:
        results = []

    # CQL search
    if "SpacePrez" in settings.ENABLED_PREZS:
        dataset_sparql_result, collection_sparql_result = await asyncio.gather(
            list_datasets(),
            list_collections(),
        )
        datasets = [
            {"id": result["id"]["value"], "title": result["label"]["value"]}
            for result in dataset_sparql_result
        ]
        collections = [
            {"id": result["id"]["value"], "title": result["label"]["value"]}
            for result in collection_sparql_result
        ]

        template_context = {
            "request": request,
            "endpoint_options": SEARCH_ENDPOINTS,
            "results": results,
            "last_search_term": search,
            "last_endpoints": endpoints,
            "datasets": datasets,
            "collections": collections,
        }
    else:
        template_context = {
            "request": request,
            "endpoint_options": SEARCH_ENDPOINTS,
            "results": results,
            "last_search_term": search,
            "last_endpoints": endpoints,
        }
    return templates.TemplateResponse("search.html", context=template_context)


@app.get("/about", summary="About page")
async def about(request: Request):
    """Displays the about page of Prez"""
    if len(settings.ENABLED_PREZS) == 1:
        if settings.ENABLED_PREZS[0] == "VocPrez":
            return await vocprez_router.about(request)
        elif settings.ENABLED_PREZS[0] == "SpacePrez":
            return await spaceprez_router.spaceprez_about(request)
        elif settings.ENABLED_PREZS[0] == "CatPrez":
            return await catprez_router.catprez_about(request)
    else:
        template_context = {"request": request}
        return templates.TemplateResponse("about.html", context=template_context)


@app.get("/prezs", summary="Enabled Prezs")
async def prezs(request: Request):
    """Returns a list of the enabled *Prez 'modules'"""
    uri = str(request.base_url)
    return JSONResponse(
        content={
            "uri": uri,
            "prezs": [f"{uri}{prez.lower()}" for prez in settings.ENABLED_PREZS],
        },
        media_type="application/json",
        headers=request.headers,
    )


@app.get("/profiles", summary="Profiles")
async def profiles(request: Request):
    """Returns a list of profiles recognised by Prez"""
    if len(settings.ENABLED_PREZS) == 1:
        if settings.ENABLED_PREZS[0] == "VocPrez":
            return await profiles_func(request, "VocPrez")
        elif settings.ENABLED_PREZS[0] == "SpacePrez":
            return await profiles_func(request, "SpacePrez")
    else:
        return await profiles_func(request)


@app.get("/object", summary="Get object", response_class=RedirectResponse)
async def object(
    request: Request,
    uri: AnyUrl,
    _profile: Optional[str] = None,
    _mediatype: Optional[str] = None,
):
    """Generic endpoint to get any object. Returns the appropriate endpoint based on type"""
    # query to get basic info for object
    sparql_response = await get_object(uri)
    if len(sparql_response) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    params = (
        str(request.query_params)
        .replace(f"&uri={quote_plus(uri)}", "")
        .replace(f"uri={quote_plus(uri)}", "")  # if uri param at start of query string
    )
    # removes the leftover "?" if no other params than uri
    if params != "":
        params = "?" + params[1:]  # will start with & instead of ?
    object_types = [URIRef(item["type"]["value"]) for item in sparql_response]
    # object_type = URIRef(sparql_response[0]["type"]["value"])

    # return according to type (IF appropriate prez module is enabled)
    for object_type in object_types:
        if object_type == SKOS.ConceptScheme:
            if "VocPrez" not in settings.ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.item_endpoint(request)
        elif object_type == SKOS.Collection:
            if "VocPrez" not in settings.ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.collection(request)
        elif object_type == SKOS.Concept:
            if "VocPrez" not in settings.ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.concept(request)
        elif object_type in [
            GEO.Feature,
            GEO.FeatureCollection,
            DCAT.Dataset,
        ]:  # TODO DCAT.Dataset will need some more thought
            if "SpacePrez" not in settings.ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return RedirectResponse(
                f"/s/object?{request.url.components.query}", headers=request.headers
            )
        # else:
    raise HTTPException(status_code=404, detail="Not Found")


@app.get("/health", summary="Health Check")
async def health(request: Request):
    """Returns the status of endpoints & connected triplestores"""
    return JSONResponse(
        content={
            "isHealthy": True,
        },
        media_type="application/json",
        headers=request.headers,
    )


if __name__ == "__main__":
    uvicorn.run("app:app", port=8000, host=settings.system_uri, reload=True)
