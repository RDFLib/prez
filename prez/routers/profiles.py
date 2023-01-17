from fastapi import APIRouter, Request
from rdflib import DCAT, URIRef
from starlette.responses import PlainTextResponse

from prez.models.profiles_listings import ProfilesMembers
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.catprez_item import CatalogItem
from prez.models.catprez_listings import CatalogMembers
from prez.renderers.renderer import (
    return_from_queries,
    return_profiles,
    return_from_graph,
)
from prez.services.sparql_queries import (
    generate_listing_construct_from_uri,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["Profiles"])


@router.get("/profiles", summary="Prez Profiles")
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
    # list_graph = profiles_graph_cache.query(list_query)
    # count_graph = profiles_graph_cache.query(count_query)
    # return await return_from_graph(
    #     list_graph + count_graph,
    #     prof_and_mt_info.mediatype,
    #     prof_and_mt_info.profile,
    #     prof_and_mt_info.profile_headers,
    #     "GenericPrez",
    # )
    return PlainTextResponse("TODO: implement profiles listing")


@router.get("/c/catalogs/{catalog_id}/{resource_id}", summary="Get Resource")
@router.get("/c/catalogs/{catalog_id}", summary="Get Catalog")
async def item_endpoint(
    request: Request, catalog_id: str = None, resource_id: str = None
):
    """Returns a CatPrez Catalog or Resource"""
    cp_item = CatalogItem(**request.path_params, url_path=str(request.url.path))
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=cp_item.classes)
    cp_item.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(cp_item.selected_class),
            prez_type="SpacePrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    item_query = generate_item_construct(cp_item, prof_and_mt_info.profile)
    item_members_query = generate_listing_construct_from_uri(
        cp_item, prof_and_mt_info.profile, 1, 20
    )
    return await return_from_queries(
        [item_query, item_members_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "CatPrez",
    )


#
#
# @router.get("/conformance", summary="Conformance")
# async def conformance(request: Request):
#     """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
#     conformance_renderer = CatPrezConformanceRenderer(request)
#     return conformance_renderer.render()
