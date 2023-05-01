import asyncio

from fastapi import APIRouter, Request
from rdflib import Graph, Literal, URIRef
from starlette.responses import PlainTextResponse

from prez.cache import search_methods
from prez.config import settings
from prez.renderers.renderer import return_rdf
from prez.sparql.methods import sparql_construct
from prez.sparql.objects_listings import (
    generate_listing_construct_from_uri,
    generate_item_construct,
)

router = APIRouter(tags=["Search"])


@router.get("/search", summary="Global Search")
@router.get("/v/search", summary="VocPrez Search")
@router.get("/c/search", summary="CatPrez Search")
@router.get("/s/search", summary="SpacePrez Search")
async def search(
    request: Request,
):
    term = request.query_params.get("term")
    limit = request.query_params.get("limit", 20)
    if not term:
        return PlainTextResponse(
            "A search_methods term must be provided as a query string argument (?term=<search_methods term>)"
        )
    start_of_path = request.url.path[:3]
    pathmap = {
        "/v/": "VocPrez",
        "/c/": "CatPrez",
        "/s/": "SpacePrez",
    }
    prez = pathmap.get(start_of_path, "all")
    selected_methods = determine_search_method(request, prez)
    # check the methods exist
    for method in selected_methods.values():
        if Literal(method) not in search_methods.keys():
            return PlainTextResponse(
                f'Search method "{method}" not found. Available methods are: '
                f"{', '.join([str(m) for m in search_methods.keys()])}"
            )
    search_queries = {}
    for prez, method in selected_methods.items():
        search_queries[prez] = search_methods[Literal(method)]
        search_queries[prez].populate_query(prez, term, limit)

    object_queries = {
        k: generate_item_construct(v, URIRef("https://w3id.org/profile/mem"))
        for k, v in search_queries.items()
    }

    results = await asyncio.gather(
        *[sparql_construct(query, p) for p, query in search_queries.items()]
    )
    # TODO update "return from queries function"
    graph = Graph(bind_namespaces="rdflib")
    graph.bind("prez", "https://prez.dev/")
    for res in results:
        g = res[1]
        graph.__iadd__(g)
    if len(graph) == 0:
        return PlainTextResponse("No results found")
    return await return_rdf(graph, mediatype="text/anot+turtle", profile_headers={})


def determine_search_method(request, prez):
    """Returns the search_methods method to use based on the request headers"""
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
    # TODO return from profiles
    methods = {}
    for prez in settings.enabled_prezs:
        methods[prez] = "jenaFTName"
    return methods
