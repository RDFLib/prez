from fastapi import Request
from rdflib import URIRef, PROF

from prez.cache import profiles_graph_cache
from prez.models.listing import ListingModel
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.renderers.renderer import return_from_graph, return_profiles
from prez.services.link_generation import _add_prez_links
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import (
    generate_listing_construct,
    generate_listing_count_construct,
)


async def listing_function(
    request: Request,
    repo: Repo,
    page: int = 1,
    per_page: int = 20,
    uri: str = None,
):
    endpoint_uri = request.scope["route"].name
    listing_item = ListingModel(
        **request.path_params,
        **request.query_params,
        endpoint_uri=endpoint_uri,
        uri=uri,
    )
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=listing_item.classes
    )
    listing_item.selected_class = prof_and_mt_info.selected_class
    listing_item.profile = prof_and_mt_info.profile

    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(listing_item.selected_class),
            prof_and_mt_info=prof_and_mt_info,
            repo=repo,
        )

    ordering_predicate = request.query_params.get("ordering-pred", None)
    item_members_query = generate_listing_construct(
        listing_item,
        prof_and_mt_info.profile,
        page=page,
        per_page=per_page,
        ordering_predicate=ordering_predicate,
    )
    count_query = generate_listing_count_construct(listing_item, endpoint_uri)
    if listing_item.selected_class in [
        URIRef("https://prez.dev/ProfilesList"),
        PROF.Profile,
    ]:
        list_graph = profiles_graph_cache.query(item_members_query).graph
        count_graph = profiles_graph_cache.query(count_query).graph
        item_graph = list_graph + count_graph
    else:
        item_graph, _ = await repo.send_queries([count_query, item_members_query], [])
    if "anot+" in prof_and_mt_info.mediatype:
        await _add_prez_links(item_graph, repo)
    return await return_from_graph(
        item_graph,
        prof_and_mt_info.mediatype,
        listing_item.profile,
        prof_and_mt_info.profile_headers,
        prof_and_mt_info.selected_class,
        repo,
    )
