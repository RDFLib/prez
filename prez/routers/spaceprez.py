from typing import Optional

from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse

from prez.routers.object import item_function, listing_function
from prez.services.curie_functions import get_uri_for_curie_id

router = APIRouter(tags=["SpacePrez"])


@router.get("/s", summary="SpacePrez Home")
async def spaceprez_profiles():
    return PlainTextResponse("SpacePrez Home")


@router.get(
    "/s/datasets",
    summary="List Datasets",
    name="https://prez.dev/endpoint/spaceprez/dataset-listing",
)
async def list_datasets(
    request: Request, page: Optional[int] = 1, per_page: Optional[int] = 20
):
    return await listing_function(request, page, per_page)


@router.get(
    "/s/datasets/{dataset_curie}/collections",
    summary="List Feature Collections",
    name="https://prez.dev/endpoint/spaceprez/feature-collection-listing",
)
async def list_feature_collections(
    request: Request,
    dataset_curie: str,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
):
    dataset_uri = get_uri_for_curie_id(dataset_curie)
    return await listing_function(request, page, per_page, uri=dataset_uri)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}/items",
    summary="List Features",
    name="https://prez.dev/endpoint/spaceprez/feature-listing",
)
async def list_features(
    request: Request,
    dataset_curie: str,
    collection_curie: str,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
):
    collection_uri = get_uri_for_curie_id(collection_curie)
    return await listing_function(request, page, per_page, uri=collection_uri)


@router.get(
    "/s/datasets/{dataset_curie}",
    summary="Get Dataset",
    name="https://prez.dev/endpoint/spaceprez/dataset",
)
async def dataset_item(request: Request, dataset_curie: str):
    return await item_function(request, object_curie=dataset_curie)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}",
    summary="Get Feature Collection",
    name="https://prez.dev/endpoint/spaceprez/feature-collection",
)
async def feature_collection_item(
    request: Request, dataset_curie: str, collection_curie: str
):
    return await item_function(request, object_curie=collection_curie)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}/items/{feature_curie}",
    summary="Get Feature",
    name="https://prez.dev/endpoint/spaceprez/feature",
)
async def feature_item(
    request: Request, dataset_curie: str, collection_curie: str, feature_curie: str
):
    return await item_function(request, object_curie=feature_curie)
