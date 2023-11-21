import re

from fastapi import APIRouter, Request, Depends
from rdflib import Literal, URIRef
from starlette.responses import PlainTextResponse

from prez.cache import search_methods
from prez.config import settings
from prez.dependencies import get_repo
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph
from prez.services.link_generation import _add_prez_links
from prez.services.curie_functions import get_uri_for_curie_id
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import generate_item_construct

router = APIRouter(tags=["Search"])


@router.get("/search", summary="Global Search")
async def search(
    request: Request,
    repo: Repo = Depends(get_repo),
):
    term = request.query_params.get("term")
    limit = request.query_params.get("limit", 20)
    offset = request.query_params.get("offset", 0)
    foc_2_filt, filt_2_foc = extract_qsa_params(request.query_params)
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
    filter_to_focus_str = ""
    focus_to_filter_str = ""

    if filt_2_foc:
        for idx, filter_pair in enumerate(filt_2_foc, start=1):
            filter_values = " ".join(f"<{f}>" for f in filter_pair[1].split(","))
            filter_to_focus_str += f"""?filter_to_focus_{idx} <{filter_pair[0]}> ?search_result_uri.
                VALUES ?filter_to_focus_{idx} {{ {filter_values} }}"""

    if foc_2_filt:
        for idx, filter_pair in enumerate(foc_2_filt, start=1):
            filter_values = " ".join(f"<{f}>" for f in filter_pair[1].split(","))
            focus_to_filter_str += f"""?search_result_uri <{filter_pair[0]}> ?focus_to_filter_{idx}.
                VALUES ?focus_to_filter_{idx} {{ {filter_values} }}"""

    predicates = (
        settings.label_predicates
        + settings.description_predicates
        + settings.provenance_predicates
    )
    predicates_sparql_string = " ".join(f"<{p}>" for p in predicates)
    search_query.populate_query(
        term,
        limit,
        offset,
        filter_to_focus_str,
        focus_to_filter_str,
        predicates_sparql_string,
    )

    full_query = generate_item_construct(
        search_query, URIRef("https://prez.dev/profile/open")
    )

    graph, _ = await repo.send_queries([full_query], [])
    graph.bind("prez", "https://prez.dev/")

    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=frozenset([PREZ.SearchResult])
    )
    if "anot+" in prof_and_mt_info.mediatype:
        await _add_prez_links(graph, repo)

    return await return_from_graph(
        graph,
        mediatype=prof_and_mt_info.mediatype,
        profile=URIRef("https://prez.dev/profile/open"),
        profile_headers=prof_and_mt_info.profile_headers,
        selected_class=prof_and_mt_info.selected_class,
        repo=repo,
    )


def extract_qsa_params(query_string_keys):
    focus_to_filter = []
    filter_to_focus = []

    for key in query_string_keys:
        if "focus-to-filter[" in key:
            predicate = re.search(r"\[(.*?)]", key).group(1)
            val = query_string_keys[key]
            if not predicate.startswith(("http://", "https://")):
                predicate = get_uri_for_curie_id(predicate)
            if not val.startswith(("http://", "https://")) and ":" in val:
                val = get_uri_for_curie_id(val)
            focus_to_filter.append((predicate, val))
        elif "filter-to-focus[" in key:
            predicate = re.search(r"\[(.*?)]", key).group(1)
            val = query_string_keys[key]
            if not predicate.startswith(("http://", "https://")):
                predicate = get_uri_for_curie_id(predicate)
            if not val.startswith(("http://", "https://")) and ":" in val:
                val = get_uri_for_curie_id(val)
            filter_to_focus.append((predicate, val))

    return focus_to_filter, filter_to_focus


def determine_search_method(request):
    """Returns the search_methods method to use based on the request headers"""
    specified_method = request.query_params.get("method")
    if specified_method:
        return specified_method
    else:
        return get_default_search_methods()


def get_default_search_methods():
    # TODO return from profiles
    return "default"
