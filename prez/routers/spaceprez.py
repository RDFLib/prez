from typing import Optional

from fastapi import APIRouter, Request
from rdflib import URIRef
from starlette.responses import PlainTextResponse

from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.spaceprez_item import SpatialItem
from prez.models.spaceprez_listings import SpatialMembers
from prez.renderers.renderer import return_from_queries, return_profiles
from prez.sparql.objects_listings import (
    generate_item_construct,
    generate_listing_construct_from_uri,
    generate_listing_count_construct,
)

router = APIRouter(tags=["SpacePrez"])


@router.get("/s", summary="SpacePrez Home")
async def spaceprez_profiles():
    return PlainTextResponse("SpacePrez Home")


@router.get("/s/datasets", summary="List Datasets")
async def list_items(
    request: Request, page: Optional[int] = 1, per_page: Optional[int] = 20
):
    """Returns a list of SpacePrez datasets in the requested profile & mediatype"""
    spatial_item = SpatialMembers(**request.path_params, url_path=str(request.url.path))
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=spatial_item.classes
    )
    spatial_item.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(spatial_item.selected_class),
            prez_type="SpacePrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    list_query, predicates_for_link_addition = generate_listing_construct_from_uri(
        spatial_item, prof_and_mt_info.profile, page, per_page
    )
    count_query = generate_listing_count_construct(spatial_item)
    return await return_from_queries(
        [list_query, count_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "SpacePrez",
        predicates_for_link_addition
    )


@router.get(
    "/s/datasets/{dataset_curie}/collections",
    summary="List Feature Collections",
)
async def list_items_feature_collections(
    request: Request, dataset_curie: str, page: int = 1, per_page: int = 20
):
    return await list_items(request, page, per_page)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}/items",
    summary="List Features",
)
async def list_items_features(
    request: Request,
    dataset_curie: str,
    collection_curie: str,
    page: int = 1,
    per_page: int = 20,
):
    return await list_items(request, page, per_page)


@router.get("/s/datasets/{dataset_curie}", summary="Get Dataset")
async def dataset_item(request: Request, dataset_curie: str):
    return await item_endpoint(request)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}",
    summary="Get Feature Collection",
)
async def feature_collection_item(
    request: Request, dataset_curie: str, collection_curie: str
):
    return await item_endpoint(request)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}/items/{feature_curie}",
    summary="Get Feature",
)
async def feature_item(
    request: Request, dataset_curie: str, collection_curie: str, feature_curie: str
):
    return await item_endpoint(request)


@router.get("/s/object")
async def item_endpoint(request: Request, spatial_item: Optional[SpatialItem] = None):
    if not spatial_item:
        spatial_item = SpatialItem(
            **request.path_params,
            **request.query_params,
            url_path=str(request.url.path)
        )
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=spatial_item.classes
    )
    spatial_item.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(spatial_item.selected_class),
            prez_type="SpacePrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    item_query = generate_item_construct(spatial_item, prof_and_mt_info.profile)
    item_members_query = generate_listing_construct_from_uri(
        spatial_item, prof_and_mt_info.profile, 1, 20
    )
    return await return_from_queries(
        [item_query, item_members_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "SpacePrez",
    )
