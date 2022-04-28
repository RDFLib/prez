import urllib.request

from fastapi import APIRouter, Request, HTTPException
import asyncio

from renderers.spaceprez import *
from services.spaceprez_service import *
from models.spaceprez import *
from utils import templates

from view_funcs import profiles_func
from config import *

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


async def home(request: Request):
    # return templates.TemplateResponse(
    #     "spaceprez/spaceprez_home.html", {"request": request}
    # )
    home_renderer = SpacePrezHomeRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
    )

    return home_renderer.render()


@router.get(
    "/spaceprez", summary="SpacePrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def spaceprez_home(request: Request):
    """Returns the SpacePrez home page in the necessary profile & mediatype"""
    return await home(request)


@router.get("/datasets", summary="List Datasets")
async def datasets(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of SpacePrez dcat:Datasets in the necessary profile & mediatype"""
    dataset_count, sparql_result = await asyncio.gather(
        count_datasets(),
        list_datasets(page, per_page)
    )
    dataset_list = SpacePrezDatasetList(sparql_result)
    dataset_list_renderer = SpacePrezDatasetListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Dataset list",
        "A list of dcat:Datasets",
        dataset_list,
        page,
        per_page,
        int(dataset_count[0]["count"]["value"])
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
async def feature_collections(
    request: Request,
    dataset_id: str,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of SpacePrez geo:FeatureCollections in the necessary profile & mediatype"""
    collection_count, sparql_result = await asyncio.gather(
        count_collections(dataset_id),
        list_collections(dataset_id, page, per_page)
    )
    feature_collection_list = SpacePrezFeatureCollectionList(sparql_result)
    feature_collection_list_renderer = SpacePrezFeatureCollectionListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "FeatureCollection list",
        "A list of geo:FeatureCollections",
        feature_collection_list,
        page,
        per_page,
        int(collection_count[0]["count"]["value"])
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

    results = await asyncio.gather(
        get_collection_construct_1(
            dataset_id=dataset_id,
            collection_id=collection_id,
            collection_uri=collection_uri,
        ),
        get_collection_construct_2(
            dataset_id=dataset_id,
            collection_id=collection_id,
            collection_uri=collection_uri,
        ),
    )

    sparql_result = Graph()
    for g in results:
        sparql_result += g

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    collection = SpacePrezFeatureCollection(
        sparql_result, id=collection_id, uri=collection_uri
    )
    collection_renderer.set_collection(collection)
    return collection_renderer.render()


# features
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/items",
    summary="List Features",
)
async def features(
    request: Request,
    dataset_id: str,
    collection_id: str,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
    feature_count, sparql_result = await asyncio.gather(
        count_features(dataset_id, collection_id),
        list_features(dataset_id, collection_id, page, per_page)
    )
    feature_list = SpacePrezFeatureList(sparql_result)
    feature_list_renderer = SpacePrezFeatureListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Feature list",
        "A list of geo:Features",
        feature_list,
        page,
        per_page,
        int(feature_count[0]["count"]["value"])
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
    pred1_str, pred2_str = '', ''
    if feature_renderer.profile == 'gas':
        pred1 = urllib.request.urlopen('https://raw.githubusercontent.com/surroundaustralia/ga-spaceprez-profile/main/simple-profiles/gas-pred1.txt')
        pred1_str = "VALUES ?p1 {" + ' '.join([f"<{line.decode()}>" for line in pred1]).replace('\n', '') + "}"
        pred2 = urllib.request.urlopen(
            'https://raw.githubusercontent.com/surroundaustralia/ga-spaceprez-profile/main/simple-profiles/gas-pred2.txt')
        pred2_str = "VALUES ?p2 {" + ' '.join([f"<{line.decode()}>" for line in pred2]).replace('\n', '') + "}"

    """convert profile to list of include / exclude filters OR additional SPARQL queries to run, pass list of predicates
     to filter on through to 'sparql_result' below"""

    sparql_result = await get_feature_construct(
        dataset_id=dataset_id,
        collection_id=collection_id,
        feature_id=feature_id,
        feature_uri=feature_uri,
        profile_filters=[pred1_str, pred2_str],
    )

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    feature = SpacePrezFeature(sparql_result, id=feature_id, uri=feature_uri)
    feature_renderer.set_feature(feature)
    return feature_renderer.render()


# feature
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/items/{feature_id}",
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
    # return templates.TemplateResponse(
    #     "spaceprez/spaceprez_conformance.html", {"request": request}
    # )
    conformance_renderer = SpacePrezConformanceRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
    )
    return conformance_renderer.render()
