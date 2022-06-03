from fastapi import APIRouter, Request, HTTPException, Query, Form
from fastapi.responses import JSONResponse, RedirectResponse
import asyncio

from renderers.spaceprez import *
from services.spaceprez_service import *
from models.spaceprez import *
from utils import templates

from view_funcs import profiles_func
from config import *
from cql_search import CQLSearch

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
        count_datasets(), list_datasets(page, per_page)
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
        int(dataset_count[0]["count"]["value"]),
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
        count_collections(dataset_id), list_collections(dataset_id, page, per_page)
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
        int(collection_count[0]["count"]["value"]),
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
    filter: Optional[str] = Query(None),
    filter_lang: Optional[str] = Query(None, alias="filter-lang"),
    filter_crs: Optional[str] = Query(None, alias="filter-crs"),
):
    """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
    if filter is not None:
        # do CQL -> SPARQL mapping
        cql_query = CQLSearch(
            filter,
            dataset_id,
            collection_id,
            filter_lang=filter_lang,
            filter_crs=filter_crs,
        ).generate_query()

        feature_count, sparql_result = await asyncio.gather(
            count_features(dataset_id, collection_id, cql_query),
            list_features(dataset_id, collection_id, page, per_page, cql_query),
        )
    else:
        feature_count, sparql_result = await asyncio.gather(
            count_features(dataset_id, collection_id),
            list_features(dataset_id, collection_id, page, per_page),
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
        int(feature_count[0]["count"]["value"]),
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
    return await profiles_func(request, "spaceprez")


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


# feature collection queryables
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/queryables",
    summary="List available query parameters for CQL search on a FeatureCollection",
)
async def feature_collection_queryables(
    request: Request, dataset_id: str, collection_id: str
):
    """Returns a list of available properties to query against using CQL search for a specific geo:FeatureCollection"""
    content = {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$id": f"{request.url.remove_query_params(keys=request.query_params.keys())}",
        "type": "object",
    }

    properties = {key: value for key, value in CQL_PROPS.items()}
    for value in properties.values():
        value.pop("qname", None)
    
    content["properties"] = properties

    # do sparql query for title & description for fc
    sparql_result = await get_collection_info_queryables(
        dataset_id=dataset_id, collection_id=collection_id, collection_uri=None
    )

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")

    content["title"] = sparql_result[0]["title"]["value"]

    if sparql_result[0].get("desc") is not None:
        content["description"] = sparql_result[0]["desc"]["value"]

    return JSONResponse(content=content)


# feature collection CQL search form
@router.post(
    "/dataset/{dataset_id}/collections/{collection_id}/cql",
    summary="Endpoint to POST CQL search form data to",
)
async def feature_collection_cql(
    request: Request,
    dataset_id: str,
    collection_id: str,
    title: Optional[str] = Form(None),
    desc: Optional[str] = Form(None),
    filter: Optional[str] = Form(None),
):
    """Handles form data from a CQL search form & redirects to /items containing the filter param"""
    filter_params = []
    if title is not None:
        filter_params.append(f'title LIKE "{title}"')
    if desc is not None:
        filter_params.append(f'desc LIKE "{desc}"')
    if filter is not None:
        filter_params.append(filter)
    return RedirectResponse(
        url=f'/dataset/{dataset_id}/collections/{collection_id}/items?filter={" AND ".join(filter_params)}',
        status_code=302,
    )
