from typing import Optional, List
from urllib.parse import quote_plus

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import AnyUrl
import uvicorn
from rdflib import URIRef
from rdflib.namespace import SKOS
from connegp import parse_mediatypes_from_accept_header
from fedsearch import SkosSearch, EndpointDetails

from config import *
from routers import vocprez_router, spaceprez_router
from services.app_service import *
from services.sparql_utils import sparql_endpoint_query
from utils import templates
from view_funcs import profiles_func


async def catch_400(request: Request, exc):
    accepts = parse_mediatypes_from_accept_header(request.headers.get("Accept"))
    if "text/html" in accepts:
        template_context = {"request": request, "message": str(exc)}
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

app.mount("/static", StaticFiles(directory="static"), name="static")
if THEME_VOLUME is not None:
    app.mount(
        f"/{THEME_VOLUME}",
        StaticFiles(directory=f"{THEME_VOLUME}/static"),
        name=THEME_VOLUME,
    )


def configure():
    configure_routing()


def configure_routing():
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


async def object_page(request: Request):
    template_context = {"request": request}
    return templates.TemplateResponse(
        "object.html", context=template_context, status_code=400
    )


@app.get("/", summary="Home page")
async def index(request: Request):
    """Displays the home page of Prez"""
    if len(ENABLED_PREZS) == 1:
        if ENABLED_PREZS[0] == "VocPrez":
            return await vocprez_router.home(request)
        elif ENABLED_PREZS[0] == "SpacePrez":
            return await spaceprez_router.home(request)
    else:
        template_context = {"request": request, "enabled_prezs": ENABLED_PREZS}
        return templates.TemplateResponse("index.html", context=template_context)


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
            if endpoint in [e['url'] for e in SEARCH_ENDPOINTS]:  # only use valid endpoints
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
            return await spaceprez_router.about(request)
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
            return await vocprez_router.scheme_endpoint(request, scheme_uri=uri)
        elif object_type == SKOS.Collection:
            if "VocPrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.collection_endpoint(request, collection_uri=uri)
        elif object_type == SKOS.Concept:
            if "VocPrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await vocprez_router.concept_endpoint(request, concept_uri=uri)
        elif object_type == DCAT.Dataset:
            if "SpacePrez" not in ENABLED_PREZS:
                raise HTTPException(status_code=404, detail="Not Found")
            return await spaceprez_router.dataset_endpoint(request, dataset_uri=uri)
        # else:
    raise HTTPException(status_code=404, detail="Not Found")
    


if __name__ == "__main__":
    configure()
    uvicorn.run("app:app", port=8000, host=SYSTEM_URI, reload=True)
else:
    configure()
