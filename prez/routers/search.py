import asyncio

from fastapi import APIRouter, Request
from rdflib import Graph
from starlette.responses import PlainTextResponse

from renderers.renderer import return_rdf
from services.sparql_queries import weighted_search
from services.sparql_utils import sparql_construct

router = APIRouter(tags=["Search"])


@router.get("/search", summary="Global Search")
@router.get("/v/search", summary="VocPrez Search")
@router.get("/c/search", summary="CatPrez Search")
@router.get("/s/search", summary="SpacePrez Search")
async def search(
    request: Request,
):
    term = request.query_params.get("term")
    if not term:
        return PlainTextResponse(
            "A search term must be provided as a query string argument (?term=<search term>)"
        )
    start_of_path = request.url.path[:3]
    pathmap = {
        "/v/": "VocPrez",
        "/c/": "CatPrez",
        "/s/": "SpacePrez",
    }
    prez = pathmap.get(start_of_path, "all")
    search_methods = determine_search_method(request, prez)
    search_functions = {
        "weighted": weighted_search,
    }
    search_queries = {
        p: search_functions[method](term, p) for p, method in search_methods.items()
    }
    results = await asyncio.gather(
        *[sparql_construct(query, p) for p, query in search_queries.items()]
    )
    # TODO update "return from queries function"
    graph = Graph(bind_namespaces="rdflib")
    for res in results:
        g = res[1]
        graph.__iadd__(g)
    return await return_rdf(graph, mediatype="text/anot+turtle", profile_headers=None)


def determine_search_method(request, prez):
    from prez.config import settings

    """Returns the search method to use based on the request headers"""
    specified_method = request.query_params.get("method")
    if specified_method:
        if prez != "all":
            return {prez: specified_method}
        else:
            return {
                prez: specified_method for prez in settings.enabled_prezs
            }  # specified method applies to all prezs
    else:
        return get_default_search_methods()


def get_default_search_methods():
    from prez.config import settings

    # TODO return from profiles
    methods = {}
    for prez in settings.enabled_prezs:
        methods[prez] = "weighted"
    return methods
