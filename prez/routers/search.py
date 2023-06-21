from fastapi import APIRouter, Request
from rdflib import Literal, URIRef
from starlette.responses import PlainTextResponse

from prez.cache import search_methods
from prez.renderers.renderer import return_rdf
from prez.sparql.methods import query_to_graph
from prez.sparql.objects_listings import generate_item_construct

router = APIRouter(tags=["Search"])


@router.get("/search", summary="Global Search")
async def search(
    request: Request,
):
    term = request.query_params.get("term")
    limit = request.query_params.get("limit", 20)
    if not term:
        return PlainTextResponse(
            status_code=400,
            content="A search_methods term must be provided as a query string argument (?term=<search_methods term>)",
        )
    selected_method = determine_search_method(request)
    if Literal(selected_method) not in search_methods.keys():
        return PlainTextResponse(
            status_code=400,
            content=f'Search method "{selected_method}" not found. Available methods are: '
            f"{', '.join([str(m) for m in search_methods.keys()])}",
        )
    search_query = search_methods[Literal(selected_method)].copy()
    search_query.populate_query(term, limit)

    full_query = generate_item_construct(
        search_query, URIRef("https://w3id.org/profile/mem")
    )

    graph = await query_to_graph(full_query)
    graph.bind("prez", "https://prez.dev/")

    return await return_rdf(graph, mediatype="text/anot+turtle", profile_headers={})


def determine_search_method(request):
    """Returns the search_methods method to use based on the request headers"""
    specified_method = request.query_params.get("method")
    if specified_method:
        return specified_method
    else:
        return get_default_search_methods()


def get_default_search_methods():
    # TODO return from profiles
    return "jenaFTName"
