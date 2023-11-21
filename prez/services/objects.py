from typing import Optional

from fastapi import Depends
from fastapi import Request, HTTPException
from rdflib import URIRef

from prez.cache import profiles_graph_cache
from prez.config import settings
from prez.dependencies import get_repo
from prez.models.object_item import ObjectItem
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph, return_profiles
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.model_methods import get_classes
from prez.services.link_generation import _add_prez_links
from prez.sparql.objects_listings import (
    generate_item_construct,
    generate_listing_construct,
)


async def object_function(
    request: Request,
    repo=Depends(get_repo),
    object_curie: Optional[str] = None,
):
    endpoint_uri = URIRef(request.scope["route"].name)
    if endpoint_uri == URIRef("https://prez.dev/endpoint/object"):
        if not request.query_params.get("uri"):
            raise HTTPException(
                status_code=400,
                detail="A URI for an object must be supplied on the /object endpoint, for example "
                "/object?uri=https://an-object-uri",
            )
        uri = URIRef(request.query_params.get("uri"))
    elif object_curie:
        uri = get_uri_for_curie_id(object_curie)
    else:
        raise HTTPException(
            status_code=400,
            detail="The 'object_curie' is required for non-object endpoints",
        )

    klasses = await get_classes(uri=uri, repo=repo, endpoint=endpoint_uri)
    # ConnegP - needs improvement
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=klasses)
    # if we're on the object endpoint and a profile hasn't been requested, use the open profile
    if (endpoint_uri == URIRef("https://prez.dev/endpoint/object")) and not (
        prof_and_mt_info.req_profiles or prof_and_mt_info.req_profiles_token
    ):
        prof_and_mt_info.selected_class = None
        prof_and_mt_info.profile = PREZ["profile/open"]
    # create the object with all required info
    object_item = ObjectItem(  # object item now does not need request
        uri=uri,
        classes=klasses,
        profile=prof_and_mt_info.profile,
        selected_class=prof_and_mt_info.selected_class,
    )
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(object_item.selected_class),
            prof_and_mt_info=prof_and_mt_info,
            repo=repo,
        )

    item_query = generate_item_construct(object_item, object_item.profile)

    ordering_predicate = request.query_params.get("ordering-pred", None)
    item_members_query = generate_listing_construct(
        object_item, prof_and_mt_info.profile, 1, 20, ordering_predicate
    )
    if object_item.selected_class == URIRef("http://www.w3.org/ns/dx/prof/Profile"):
        item_graph = profiles_graph_cache.query(item_query).graph
        if item_members_query:
            list_graph = profiles_graph_cache.query(item_members_query).graph
            item_graph += list_graph
    else:
        item_graph, _ = await repo.send_queries([item_query, item_members_query], [])
    if "anot+" in prof_and_mt_info.mediatype:
        await _add_prez_links(item_graph, repo)
    return await return_from_graph(
        item_graph,
        prof_and_mt_info.mediatype,
        object_item.profile,
        prof_and_mt_info.profile_headers,
        prof_and_mt_info.selected_class,
        repo,
    )
