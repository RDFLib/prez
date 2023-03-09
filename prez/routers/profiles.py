from fastapi import APIRouter, Request
from rdflib import URIRef

from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.profiles_item import ProfileItem
from prez.models.profiles_listings import ProfilesMembers
from prez.cache import profiles_graph_cache
from prez.renderers.renderer import return_profiles, return_from_graph
from prez.sparql.objects_listings import (
    generate_listing_construct_from_uri,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["Profiles"])


@router.get("/profiles", summary="Prez Profiles")
@router.get("/s/profiles", summary="SpacePrez Profiles")
@router.get("/v/profiles", summary="SpacePrez Profiles")
@router.get("/c/profiles", summary="SpacePrez Profiles")
async def profiles(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    profiles_members = ProfilesMembers(url_path=str(request.url.path))
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=profiles_members.classes
    )
    profiles_members.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(profiles_members.selected_class),
            prez_type="GenericPrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    list_query = generate_listing_construct_from_uri(
        profiles_members, prof_and_mt_info.profile, page, per_page
    )
    count_query = generate_listing_count_construct(profiles_members)
    # TODO len(profiles_graph_cache) = 0 ; handle directing the queries to the local graphs via the `sparql_construct`
    #  function
    list_graph = profiles_graph_cache.query(list_query).graph
    count_graph = profiles_graph_cache.query(count_query).graph
    return await return_from_graph(
        list_graph + count_graph,
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "GenericPrez",
    )


@router.get("/profiles/{profile_id}", summary="Profile")
async def profile(request: Request, profile_id: str):
    """Returns list of the profiles which constrain SpacePrez classes"""
    profiles_item = ProfileItem(id=profile_id)
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=profiles_item.classes
    )
    profiles_item.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(profiles_item.selected_class),
            prez_type="GenericPrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    profile_query = generate_item_construct(profiles_item, prof_and_mt_info.profile)
    profile_graph = profiles_graph_cache.query(profile_query).graph
    return await return_from_graph(
        profile_graph,
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "GenericPrez",
    )
