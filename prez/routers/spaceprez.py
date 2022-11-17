from typing import Optional

from fastapi import APIRouter, Request
from rdflib import Namespace

from prez.models.spaceprez_item import SpatialItem
from prez.profiles.generate_profiles import get_profile_and_mediatype
from prez.renderers.renderer import return_data
from prez.services.connegp_service import get_requested_profile_and_mediatype
from prez.services.sparql_new import generate_item_construct, generate_listing_construct

PREZ = Namespace("https://kurrawong.net/prez/")

router = APIRouter(tags=["SpacePrez"])


@router.get("/s/profiles", summary="SpacePrez Profiles")
async def spaceprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by SpacePrez"""
    pass


@router.get("/s/datasets", summary="List Datasets")
async def list_items(
    request: Request, page: Optional[int] = 1, per_page: Optional[int] = 20
):
    """Returns a list of SpacePrez datasets in the requested profile & mediatype"""
    general_item = SpatialItem(**request.path_params, url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    profile, mediatype = get_profile_and_mediatype(
        general_item.classes, req_profiles, req_mediatypes
    )
    query = generate_listing_construct(general_item, profile, page, per_page)
    return await return_data(query, mediatype, profile, "SpacePrez")


@router.get(
    "/s/datasets/{dataset_id}/collections",
    summary="List Feature Collections",
)
async def list_items_feature_collections(
    request: Request, dataset_id: str, page: int = 1, per_page: int = 20
):
    return await list_items(request, page, per_page)


@router.get(
    "/s/datasets/{dataset_id}/collections/{collection_id}/items",
    summary="List Features",
)
async def list_items_features(
    request: Request,
    dataset_id: str,
    collection_id: str,
    page: int = 1,
    per_page: int = 20,
):
    return await list_items(request, page, per_page)


@router.get("/s/datasets/{dataset_id}", summary="Get Dataset")
async def dataset_item(request: Request, dataset_id: str):
    return await item_endpoint(request)


@router.get(
    "/s/datasets/{dataset_id}/collections/{collection_id}",
    summary="Get Feature Collection",
)
async def feature_collection_item(
    request: Request, dataset_id: str, collection_id: str
):
    return await item_endpoint(request)


@router.get(
    "/s/datasets/{dataset_id}/collections/{collection_id}/items/{feature_id}",
    summary="Get Feature",
)
async def feature_item(
    request: Request, dataset_id: str, collection_id: str, feature_id: str
):
    return await item_endpoint(request)


@router.get("/s/object")
async def item_endpoint(request: Request):
    item = SpatialItem(
        **request.path_params, **request.query_params, url_path=str(request.url.path)
    )
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    profile, mediatype = get_profile_and_mediatype(
        item.classes, req_profiles, req_mediatypes
    )
    query = generate_item_construct(item, profile)
    response = await return_data(query, mediatype, profile, "SpacePrez")
    return response
