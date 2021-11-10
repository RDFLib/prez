from typing import Optional, List
from urllib.parse import quote_plus

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn
from rdflib.namespace import SKOS
from rdflib import URIRef
from fedsearch import SkosSearch, EndpointDetails

from config import *
from routers import vocprez_router
from services.app_service import *
from services.sparql_utils import sparql_endpoint_query
from utils import templates
from view_funcs import profiles_func

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


def build_cache():
    # needs to depend on what *Prezs are enabled

    # 1. query DB for seeAlso map
    # get index dict of graph & admin graph URIs
    # system_index = {
    #     "vocab_uri": [
    #         "background_uri",
    #         "vocab_system_uri"
    #     ]
    # }
    #
    pass


def configure():
    build_cache()
    configure_routing()


def configure_routing():
    if "VocPrez" in ENABLED_PREZS:
        app.include_router(vocprez_router.router)


@app.get("/", summary="Home page")
async def index(request: Request):
    """Displays the home page of Prez"""
    if len(ENABLED_PREZS) == 1:
        if ENABLED_PREZS[0] == "VocPrez":
            return await vocprez_router.home(request)
    else:
        template_context = {"request": request, "enabled_prezs": ENABLED_PREZS}
        return templates.TemplateResponse("index.html", context=template_context)


# @app.get("/sparql", summary="SPARQL page", include_in_schema=False)
# async def sparql(request: Request):
#     """Displays the sparql page of Prez"""
#     template_context = {"request": request}
#     return templates.TemplateResponse("sparql.html", context=template_context)


@app.get("/sparql", summary="SPARQL Endpoint")
async def sparql_get(request: Request, query: Optional[str] = None):
    accepts = request.headers.get("accept")
    if accepts is not None:
        top_accept = accepts.split(",")[0].split(";")[0]
        if top_accept == "text/html":
            return templates.TemplateResponse("sparql.html", {"request": request})
        else:
            query = request.query_params.get("query")
            if query is not None:
                if "CONSTRUCT" in query or "DESCRIBE" in query:
                    sparql_result = await sparql_endpoint_query(
                        query, accept=top_accept
                    )
                    return Response(content=sparql_result[1], media_type=top_accept)
                else:
                    sparql_result = await sparql_endpoint_query(query)
                    return JSONResponse(
                        content=sparql_result[1],
                        media_type="application/sparql-results+json",
                    )
            else:
                return Response(content="SPARQL service description")


@app.post("/sparql", summary="SPARQL Endpoint")
async def sparql_post(request: Request):
    content_type = request.headers.get("content-type")
    accepts = request.headers.get("accept")
    top_accept = accepts.split(",")[0].split(";")[0]
    if content_type == "application/x-www-form-urlencoded":
        formdata = await request.form()
        query = formdata.get("query")
    else:
        query_bytes = await request.body()
        query = query_bytes.decode()
    if query is not None:
        if "CONSTRUCT" in query or "DESCRIBE" in query:
            sparql_result = await sparql_endpoint_query(query, accept=top_accept)
            return Response(content=sparql_result[1], media_type=top_accept)
        else:
            sparql_result = await sparql_endpoint_query(query)
            return JSONResponse(
                content=sparql_result[1], media_type="application/sparql-results+json"
            )
    else:
        return Response(content="SPARQL service description")


@app.get("/search", summary="Search page")
async def search(
    request: Request,
    search: Optional[str] = None,
    endpoints: List[str] = Query(["self"]),
):
    """Displays the search page of Prez"""
    if search is not None and search != "":
        self_sparql_endpoint = str(request.base_url)[:-1] + app.router.url_path_for(
            "sparql_get"
        )
        endpoint_details = []
        for endpoint in endpoints:
            if endpoint in [e[0] for e in SEARCH_ENDPOINTS]: # only use valid endpoints
                if endpoint == "self":
                    endpoint_details.append(
                        EndpointDetails(self_sparql_endpoint, None, None)
                    )
                else:
                    endpoint_details.append(EndpointDetails(endpoint, None, None))
        s = await SkosSearch.federated_search(search, "preflabel", endpoint_details)
        results = SkosSearch.combine_search_results(s, "preflabel")
    else:
        results = []
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
    else:
        return await profiles_func(request)


@app.get("/object", summary="Get object", response_class=RedirectResponse)
async def object(
    request: Request,
    uri: str,
    _profile: Optional[str] = None,
    _mediatype: Optional[str] = None,
):
    """Generic endpoint to get any object. Returns the appropriate endpoint based on type"""
    # query to get basic info for object
    sparql_response = await get_object(uri)
    params = (
        str(request.query_params)
        .replace(f"&uri={quote_plus(uri)}", "")
        .replace(f"uri={quote_plus(uri)}", "")  # if uri param at start of query string
    )
    # removes the leftover "?" if no other params than uri
    if params != "":
        params = "?" + params[1:]  # will start with & instead of ?
    object_type = URIRef(sparql_response[0]["type"]["value"])
    # object_id = sparql_response[0]["id"]["value"]
    # object_cs_id = (
    #     sparql_response[0]["cs_id"]["value"]
    #     if sparql_response[0].get("cs_id") is not None
    #     else None
    # )

    # redirect according to type (IF appropriate prez module is enabled)
    if object_type == SKOS.ConceptScheme:
        if "VocPrez" not in ENABLED_PREZS:
            raise HTTPException(status_code=404, detail="This resource does not exist")
        # return RedirectResponse(
        #     f"{vocprez_router.router.url_path_for('scheme', scheme_id=object_id)}{params}",
        #     headers=request.headers,
        # )
        return await vocprez_router.scheme_endpoint(request, scheme_uri=uri)
    elif object_type == SKOS.Collection:
        if "VocPrez" not in ENABLED_PREZS:
            raise HTTPException(status_code=404, detail="This resource does not exist")
        return await vocprez_router.collection_endpoint(request, collection_uri=uri)
    elif object_type == SKOS.Concept:
        if "VocPrez" not in ENABLED_PREZS:
            raise HTTPException(status_code=404, detail="This resource does not exist")
        return await vocprez_router.concept_endpoint(request, concept_uri=uri)
    else:
        raise HTTPException(status_code=404, detail="This resource does not exist")


if __name__ == "__main__":
    configure()
    uvicorn.run("app:app", port=PORT, host=SYSTEM_URI, reload=True)
else:
    configure()
