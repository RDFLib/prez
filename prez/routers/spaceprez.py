from typing import Optional

from fastapi import APIRouter, Request, Depends
from starlette.responses import PlainTextResponse

from prez.dependencies import get_repo
from prez.services.objects import object_function
from prez.services.listings import listing_function
from prez.services.curie_functions import get_uri_for_curie_id
from prez.sparql.methods import Repo

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
    request: Request,
    repo: Repo = Depends(get_repo),
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
):
    return await listing_function(
        request=request, page=page, per_page=per_page, repo=repo
    )


@router.get(
    "/s/datasets/{dataset_curie}/collections",
    summary="List Feature Collections",
    name="https://prez.dev/endpoint/spaceprez/feature-collection-listing",
)
async def list_feature_collections(
    request: Request,
    dataset_curie: str,
    repo: Repo = Depends(get_repo),
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
):
    dataset_uri = get_uri_for_curie_id(dataset_curie)
    return await listing_function(
        request=request,
        page=page,
        per_page=per_page,
        uri=dataset_uri,
        repo=repo,
    )


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}/items",
    summary="List Features",
    name="https://prez.dev/endpoint/spaceprez/feature-listing",
)
async def list_features(
    request: Request,
    dataset_curie: str,
    collection_curie: str,
    repo: Repo = Depends(get_repo),
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
):
    collection_uri = get_uri_for_curie_id(collection_curie)
    return await listing_function(
        request=request,
        page=page,
        per_page=per_page,
        uri=collection_uri,
        repo=repo,
    )


@router.get(
    "/s/datasets/{dataset_curie}",
    summary="Get Dataset",
    name="https://prez.dev/endpoint/spaceprez/dataset",
)
async def dataset_item(
    request: Request,
    dataset_curie: str,
    repo: Repo = Depends(get_repo),
):
    return await object_function(request, object_curie=dataset_curie, repo=repo)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}",
    summary="Get Feature Collection",
    name="https://prez.dev/endpoint/spaceprez/feature-collection",
)
async def feature_collection_item(
    request: Request,
    dataset_curie: str,
    collection_curie: str,
    repo: Repo = Depends(get_repo),
):
    return await object_function(request, object_curie=collection_curie, repo=repo)


@router.get(
    "/s/datasets/{dataset_curie}/collections/{collection_curie}/items/{feature_curie}",
    summary="Get Feature",
    name="https://prez.dev/endpoint/spaceprez/feature",
)
async def feature_item(
    request: Request,
    dataset_curie: str,
    collection_curie: str,
    feature_curie: str,
    repo: Repo = Depends(get_repo),
):
    return await object_function(request=request, object_curie=feature_curie, repo=repo)
