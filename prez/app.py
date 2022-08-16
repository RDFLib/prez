import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import httpx
import uvicorn
from connegp import parse_mediatypes_from_accept_header
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fedsearch import SkosSearch, EndpointDetails
from pydantic import AnyUrl
from starlette.middleware.cors import CORSMiddleware

from prez.profiles.generate_profiles import get_general_profiles
from prez.routers import catprez_router, vocprez_router, spaceprez_router
from prez.routers.vocprez_router import vocprez_home_endpoint
from prez.services.app_service import *
from prez.services.spaceprez_service import list_datasets, list_collections
from prez.utils import templates
from prez.view_funcs import profiles_func
from textwrap import dedent


async def catch_400(request: Request, exc):
    accepts = parse_mediatypes_from_accept_header(request.headers.get("Accept"))
    if "text/html" in accepts:
        template_context = {"request": request, "message": exc.detail}
        return templates.TemplateResponse(
            "400.html", context=template_context, status_code=400
        )
    else:
        return JSONResponse(content={"detail": exc}, status_code=400)


async def catch_404(request: Request, exc):
    accepts = parse_mediatypes_from_accept_header(request.headers.get("Accept"))
    if "text/html" in accepts:
        template_context = {"request": request}
        return templates.TemplateResponse(
            "404.html", context=template_context, status_code=404
        )
    else:
        return JSONResponse(content={"detail": str(exc.detail)}, status_code=404)


async def catch_500(request: Request, exc):
    accepts = parse_mediatypes_from_accept_header(request.headers.get("Accept"))
    if "text/html" in accepts:
        template_context = {"request": request}
        return templates.TemplateResponse(
            "500.html", context=template_context, status_code=500
        )
    else:
        return JSONResponse(
            content={"detail": "Internal Server Error"}, status_code=500
        )


app = FastAPI(
    exception_handlers={
        400: catch_400,
        404: catch_404,
        500: catch_500,
    }
)

app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
if THEME_VOLUME is not None:
    app.mount(
        f"/theme",
        StaticFiles(directory=Path(__file__).parent / f"{THEME_VOLUME}" / "static"),
        name="theme",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def configure():
    configure_routing()


def configure_routing():
    if "CatPrez" in ENABLED_PREZS:
        app.include_router(catprez_router.router)
    if "VocPrez" in ENABLED_PREZS:
        app.include_router(vocprez_router.router)
    if "SpacePrez" in ENABLED_PREZS:
        app.include_router(spaceprez_router.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    if str(request.url).endswith("object"):
        return await object_page(request)
    else:
        return await catch_400(request, exc)


@app.on_event("startup")
async def app_startup():
    """
    This function runs at startup and will continually poll the separate backends until their SPARQL endpoints
    are available. Initial caching can be triggered within the try block. NB this function does not check that data is
    appropriately configured at the SPARQL endpoint(s), only that the SPARQL endpoint(s) are reachable.
    """
    prez2endpoint = {
        "SpacePrez": SPACEPREZ_SPARQL_ENDPOINT,
        "VocPrez": VOCPREZ_SPARQL_ENDPOINT,
        "TimePrez": TIMEPREZ_SPARQL_ENDPOINT,
        "CatPrez": CATPREZ_SPARQL_ENDPOINT,
    }
    if len(ENABLED_PREZS) > 0:
        for prez in ENABLED_PREZS:
            connected_to_prez_flavour = False
            while not connected_to_prez_flavour:
                try:
                    print(f"Trying endpoint {prez2endpoint[prez]}")
                    response = httpx.head(prez2endpoint[prez])
                    response.raise_for_status()
                    if response.reason_phrase == "OK":
                        print(
                            f"Successfully connected to {prez} endpoint {prez2endpoint[prez]}"
                        )
                        # Check whether there are any remote profiles, and if so, cache them.
                        # If there will be remote profiles but they haven't yet been loaded to fuseki, they will be not be
                        # cached at startup, but will be cached after any endpoint using profiles is called.
                        query_for_profiles = """PREFIX prof: <http://www.w3.org/ns/dx/prof/>
                                                DESCRIBE ?profile { ?profile a prof:Profile } LIMIT 1"""
                        query_success, profiles_g = await sparql_construct(
                            query_for_profiles, prez
                        )
                        if query_success and len(profiles_g) > 0:
                            print(f"Profiles found in data store for {prez}, caching them")
                            if prez == "CatPrez":
                                get_general_profiles(DCAT.Dataset)
                                get_general_profiles(DCAT.Resource)
                            if prez == "SpacePrez":
                                get_general_profiles(DCAT.Dataset)
                                get_general_profiles(GEO.FeatureCollection)
                                get_general_profiles(GEO.Feature)
                            if prez == "VocPrez":
                                pass
                        else:
                            print(
                                f"No profiles found in data store for {prez}, continuing with startup"
                            )
                        connected_to_prez_flavour = True
                    else:
                        raise httpx.HTTPError
                        # are there any non "OK" responses that would *not* raise for status?
                except httpx.HTTPError as exc:
                    print(f"HTTP Exception for {exc.request.url} - {exc}")
                    print(f"Failed to connect to {prez} endpoint {prez2endpoint[prez]}")
                    print("retrying in 3 seconds...")
                    time.sleep(3)
    else:
        raise ValueError(
            'No Prezs enabled - set "ENABLED_PREZS" environment variable to a list of enabled Prezs'
        )


@app.get("/purge-cache", summary="Purge LRU and ALRU caches")
async def purge_cache():
    import gc
    import functools

    objects = [
        i for i in gc.get_objects() if isinstance(i, functools._lru_cache_wrapper)
    ]
    # All objects cleared
    for object in objects:
        object.cache_clear()

    from async_lru import _cache_clear
    from prez.profiles.generate_profiles import (
        retrieve_relevant_shapes,
        get_general_profiles,
        get_class_based_and_default_profiles,
        create_profiles_graph,
    )
    from prez.routers.spaceprez_router import (
        spaceprez_home_endpoint,
        dataset_endpoint,
        datasets_endpoint,
        feature_endpoint,
        features_endpoint,
        feature_collection_endpoint,
        feature_collections_endpoint,
    )
    from prez.services.spaceprez_service import (
        list_features,
        list_collections,
        list_datasets,
        count_features,
        count_collections,
        count_datasets,
        get_dataset_construct,
        get_feature_construct,
        get_collection_construct_1,
        get_collection_construct_2,
        get_object_uri_and_classes,
    )
    from prez.view_funcs import profiles_func

    funclist = [
        list_collections,
        list_datasets,
        count_collections,
        count_datasets,
        get_dataset_construct,
        get_collection_construct_1,
        get_collection_construct_2,
        get_object_uri_and_classes,
        get_general_profiles,
        create_profiles_graph,
        profiles_func,
        dataset_endpoint,
        datasets_endpoint,
        feature_collection_endpoint,
        feature_collections_endpoint,
        features_endpoint,
        feature_endpoint,
        get_class_based_and_default_profiles,
        retrieve_relevant_shapes,
        spaceprez_home_endpoint,
        vocprez_home_endpoint,
        about,
        count_features,
        list_features,
        get_feature_construct,
    ]
    for func in funclist:
        _cache_clear(func)
    return "cache purged"


async def object_page(request: Request):
    template_context = {"request": request}
    return templates.TemplateResponse(
        "object.html", context=template_context, status_code=400
    )


@app.get("/", summary="Home page")
async def index(request: Request):
    """Displays the home page of Prez"""
    if len(ENABLED_PREZS) == 1:
        if ENABLED_PREZS[0] == "CatPrez":
            return await catprez_router.home(request)
        elif ENABLED_PREZS[0] == "VocPrez":
            return await vocprez_router.home(request)
        elif ENABLED_PREZS[0] == "SpacePrez":
            return await spaceprez_router.spaceprez_home_endpoint(request)
    else:
        template_context = {"request": request, "enabled_prezs": ENABLED_PREZS}
        return templates.TemplateResponse("index.html", context=template_context)


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
    """.format(request.url_for("sparql_get"))
    if format == "text/turtle":
        return dedent(ttl)
    else:
        return Graph().parse(data=ttl).serialize(format=format)


@app.get("/sparql", summary="SPARQL Endpoint")
async def sparql_get(request: Request, query: Optional[str] = None):
    accept = request.query_params.get("accept") if request.query_params.get("accept") is not None else request.query_params.get("Accept")
    if accept is not None:
        if " " in accept:
            accept = accept.replace(" ", "+")
    else:  # accept is None:
        accepts = request.headers.get("accept")
        if accepts is not None:
            accept = accepts.split(",")[0].split(";")[0]

    if accept == "text/html":
        return templates.TemplateResponse("sparql.html", {"request": request})

    # fallback - can't find an accept value
    if accept is None:
        accept = "application/sparql-results+json"

    query = request.query_params.get("query")

    if query is not None:
        sparql_result = await sparql_endpoint_query_multiple(query, accept=accept)
        if len(sparql_result[1]) > 0 and not ALLOW_PARTIAL_RESULTS:
            error_list = "\n".join([
                f"Error code {e['code']} in {e['prez']}: {e['message']}\n"
                for e in sparql_result[1]
            ])
            Response(
                content=f"SPARQL query error:\n{error_list}",
                media_type="text/plain"
            )
        else:
            if accept in RDF_MEDIATYPES:
                return Response(
                    content=sparql_result[0],
                    media_type=accept
                )
            elif accept in ["application/sparql-results+json", "application/json"]:
                return JSONResponse(
                    content=sparql_result[0],
                    media_type="application/sparql-results+json",
                )
            else:
                return Response(
                    content=sparql_result[0],
                    media_type=accept,
                    headers={
                        "content-disposition": "attachment; filename=result.xml"
                    }
                )
    else:
        return Response(content=_get_sparql_service_description(request, accept))


@app.post("/sparql", summary="SPARQL Endpoint")
async def sparql_post(request: Request):
    accept = request.query_params.get("accept") if request.query_params.get("accept") is not None else request.query_params.get("Accept")
    if accept is not None:
        if " " in accept:
            accept = accept.replace(" ", "+")
    else:  # accept is None:
        accepts = request.headers.get("accept")
        if accepts is not None:
            accept = accepts.split(",")[0].split(";")[0]

    # fallback - can't find an accept value
    if accept is None:
        accept = "application/sparql-results+json"

    if request.headers.get("content-type") == "application/x-www-form-urlencoded":
        formdata = await request.form()
        query = formdata.get("query")
    else:
        query_bytes = await request.body()
        query = query_bytes.decode()

    if query is not None:
        sparql_result = await sparql_endpoint_query_multiple(query, accept=accept)
        if len(sparql_result[1]) > 0 and not ALLOW_PARTIAL_RESULTS:
            error_list = "\n".join([
                f"Error code {e['code']} in {e['prez']}: {e['message']}\n"
                for e in sparql_result[1]
            ])
            Response(
                content=f"SPARQL query error:\n{error_list}",
                media_type="text/plain"
            )
        else:
            if accept in RDF_MEDIATYPES:
                return Response(
                    content=sparql_result[0],
                    media_type=accept
                )
            elif accept in ["application/sparql-results+json", "application/json"]:
                return JSONResponse(
                    content=sparql_result[0],
                    media_type="application/sparql-results+json",
                )
            else:
                return Response(
                    content=sparql_result[0],
                    media_type=accept,
                    headers={
                        "content-disposition": "attachment; filename=result.xml"
                    }
                )
    else:
        return Response(content=_get_sparql_service_description(request, accept))


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
    if "SpacePrez" in ENABLED_PREZS:
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
    if len(ENABLED_PREZS) == 1:
        if ENABLED_PREZS[0] == "VocPrez":
            return await vocprez_router.about(request)
        elif ENABLED_PREZS[0] == "SpacePrez":
            return await spaceprez_router.spaceprez_about(request)
        elif ENABLED_PREZS[0] == "CatPrez":
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
            "prezs": [f"{uri}{prez.lower()}" for prez in ENABLED_PREZS],
        },
        media_type="application/json",
        headers=request.headers,
    )


@app.get("/profiles", summary="Profiles")
async def profiles(request: Request):
    """Returns a list of profiles recognised by Prez"""
    if len(ENABLED_PREZS) == 1:
        if ENABLED_PREZS[0] == "VocPrez":
            return await profiles_func(request, "VocPrez")
        elif ENABLED_PREZS[0] == "SpacePrez":
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
            if "VocPrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.scheme(request)
        elif object_type == SKOS.Collection:
            if "VocPrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.collection(request)
        elif object_type == SKOS.Concept:
            if "VocPrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.concept(request)
        elif object_type == DCAT.Dataset:
            if "SpacePrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await spaceprez_router.dataset(request)
        elif object_type == GEO.FeatureCollection:
            if "SpacePrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await spaceprez_router.feature_collection(request)
        elif object_type == GEO.Feature:
            if "SpacePrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await spaceprez_router.feature(request)
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
    configure()
    uvicorn.run("app:app", port=8000, host=SYSTEM_URI, reload=True)
else:
    configure()
