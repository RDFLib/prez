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
    sparql_result = await list_datasets()
    dataset_list = SpacePrezDatasetList(sparql_result)
    dataset_list_renderer = SpacePrezDatasetListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Dataset list",
        "A list of dcat:Datasets",
        dataset_list,
    )
    return dataset_list_renderer.render()


@router.get("/dataset/{dataset_id}", summary="Get Dataset")
async def dataset(request: Request, dataset_id: str):
    """Returns a SpacePrez dcat:Dataset in the necessary profile & mediatype"""
    return await dataset_endpoint(request, dataset_id=dataset_id)


async def dataset_endpoint(
    request: Request,
    dataset_id: Optional[str] = None,
    dataset_uri: Optional[str] = None,
):
    dataset_renderer = SpacePrezDatasetRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
    )

    sparql_result = await get_dataset_construct(
        dataset_id=dataset_id,
        dataset_uri=dataset_uri,
    )

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    dataset = SpacePrezDataset(sparql_result, id=dataset_id, uri=dataset_uri)
    dataset_renderer.set_dataset(dataset)
    return dataset_renderer.render()


# feature collections
@router.get("/dataset/{dataset_id}/collections", summary="List FeatureCollections")
async def feature_collections(request: Request, dataset_id: str):
    """Returns a list of SpacePrez geo:FeatureCollections in the necessary profile & mediatype"""
    sparql_result = await list_collections(dataset_id)
    feature_collection_list = SpacePrezFeatureCollectionList(sparql_result)
    feature_collection_list_renderer = SpacePrezFeatureCollectionListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "FeatureCollection list",
        "A list of geo:FeatureCollections",
        feature_collection_list,
    )
    return feature_collection_list_renderer.render()


# feature collection
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}",
    summary="Get FeatureCollections",
)
async def feature_collection(request: Request, dataset_id: str, collection_id: str):
    """Returns a SpacePrez geo:FeatureCollection in the necessary profile & mediatype"""
    return await feature_collection_endpoint(
        request, dataset_id=dataset_id, collection_id=collection_id
    )


async def feature_collection_endpoint(
    request: Request,
    dataset_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
):
    collection_renderer = SpacePrezFeatureCollectionRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
    )

    sparql_result = await get_collection_construct(
        dataset_id=dataset_id,
        collection_id=collection_id,
        collection_uri=collection_uri,
    )

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    collection = SpacePrezFeatureCollection(
        sparql_result, id=collection_id, uri=collection_uri
    )
    collection_renderer.set_collection(collection)
    return collection_renderer.render()


# features
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/features",
    summary="List Features",
)
async def features(request: Request, dataset_id: str, collection_id: str):
    """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
    sparql_result = await list_features(dataset_id, collection_id)
    feature_list = SpacePrezFeatureList(sparql_result)
    feature_list_renderer = SpacePrezFeatureListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Feature list",
        "A list of geo:Features",
        feature_list,
    )
    return feature_list_renderer.render()


async def feature_endpoint(
    request: Request,
    dataset_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    feature_uri: Optional[str] = None,
):
    feature_renderer = SpacePrezFeatureRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
    )

    sparql_result = await get_feature_construct(
        dataset_id=dataset_id,
        collection_id=collection_id,
        feature_id=feature_id,
        feature_uri=feature_uri,
    )
    print(sparql_result.serialize())

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    feature = SpacePrezFeature(sparql_result, id=feature_id, uri=feature_uri)
    feature_renderer.set_feature(feature)
    return feature_renderer.render()


# feature
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/features/{feature_id}",
    summary="Get Feature",
)
async def feature(
    request: Request, dataset_id: str, collection_id: str, feature_id: str
):
    """Returns a SpacePrez geo:Feature in the necessary profile & mediatype"""
    return await feature_endpoint(
        request,
        dataset_id=dataset_id,
        collection_id=collection_id,
        feature_id=feature_id,
    )


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
@router.get("/conformance", summary="Conformance")
async def conformance(request: Request):
    """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
    return templates.TemplateResponse(
        "spaceprez/spaceprez_conformance.html", {"request": request}
    )
