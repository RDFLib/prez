from fastapi import APIRouter, Request, HTTPException

from renderers.spaceprez import *
from services.spaceprez_service import *
from models.spaceprez import *
from utils import templates

from view_funcs import profiles_func
from config import *

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


async def home(request: Request):
    # dataset_renderer = SpacePrezDatasetRenderer(
    #     request, str(request.url.remove_query_params(keys=request.query_params.keys()))
    # )
    # sparql_result = await get_dataset_construct()
    # dataset = SpacePrezDataset(sparql_result)
    # dataset_renderer.set_dataset(dataset)
    # return dataset_renderer.render()
    return templates.TemplateResponse(
        "spaceprez/spaceprez_home.html", {"request": request}
    )


@router.get(
    "/spaceprez", summary="SpacePrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def spaceprez_home(request: Request):
    """Returns the SpacePrez home page in the necessary profile & mediatype"""
    return await home(request)


@router.get("/datasets", summary="List Datasets")
async def datasets(request: Request):
    """Returns a list of SpacePrez dcat:Datasets in the necessary profile & mediatype"""
    return "datasets"


@router.get("/dataset/{dataset_id}", summary="Get Dataset")
async def dataset(request: Request, dataset_id: str):
    """Returns a SpacePrez dcat:Dataset in the necessary profile & mediatype"""
    return f"dataset {dataset_id}"


# feature collections
@router.get("/dataset/{dataset_id}/collections", summary="List FeatureCollections")
async def feature_collections(request: Request, dataset_id: str):
    """Returns a list of SpacePrez geo:FeatureCollections in the necessary profile & mediatype"""
    return "featurecollections"


# feature collection
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}",
    summary="Get FeatureCollections",
)
async def feature_collection(request: Request, dataset_id: str, collection_id: str):
    """Returns a SpacePrez geo:FeatureCollection in the necessary profile & mediatype"""
    return "featurecollection"


# features
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/features",
    summary="List Features",
)
async def features(request: Request, dataset_id: str, collection_id: str):
    """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
    return "features"


# feature
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/features/{feature_id}",
    summary="Get Feature",
)
async def feature(
    request: Request, dataset_id: str, collection_id: str, feature_id: str
):
    """Returns a SpacePrez geo:Feature in the necessary profile & mediatype"""
    return "feature"


# about
async def about(request: Request):
    return templates.TemplateResponse(
        "spaceprez/spaceprez_about.html", {"request": request}
    )


@router.get(
    "/spaceprez-about",
    summary="SpacePrez About",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def spaceprez_about(request: Request):
    """Returns the SpacePrez about page in the necessary profile & mediatype"""
    return await about(request)


# profiles
@router.get(
    "/spaceprez-profiles",
    summary="SpacePrez Profiles",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def spaceprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by SpacePrez"""
    return await profiles_func(request, "SpacePrez")


# conform
@router.get(
    "/conformance", summary="Conformance", include_in_schema=len(ENABLED_PREZS) > 1
)
async def conformance(request: Request):
    """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
    return templates.TemplateResponse(
        "spaceprez/spaceprez_conformance.html", {"request": request}
    )
