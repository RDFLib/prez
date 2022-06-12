from fastapi import APIRouter, Request, HTTPException

from prez.models.spaceprez import *
from prez.profiles.generate_profiles import (
    ProfileDetails,
    retrieve_relevant_shapes,
    build_alt_graph,
    apply_profile,
)
from prez.renderers.spaceprez import *
from prez.services.spaceprez_service import *
from prez.utils import templates
from prez.view_funcs import profiles_func

PREZ = Namespace("https://surroundaustralia.com/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


@alru_cache(maxsize=5)
@router.get(
    "/spaceprez", summary="SpacePrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def spaceprez_home_endpoint(request: Request):
    """Returns the SpacePrez home page in the necessary profile & mediatype"""
    home_renderer = SpacePrezHomeRenderer(request)
    if home_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            PREZ.SpacePrezHome,
            home_renderer.profile_details.profiles_formats,
            home_renderer.profile_details.available_profiles_dict,
        )
        return home_renderer.render(alt_profiles_graph=alt_profiles_graph)
    return home_renderer.render()


@alru_cache(maxsize=5)
@router.get("/datasets", summary="List Datasets")
async def datasets_endpoint(
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
        PREZ.DatasetList,
        page,
        per_page,
        int(dataset_count[0]["count"]["value"]),
        dataset_list,
    )
    if dataset_list_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(dataset_list_renderer.instance_uri),
            dataset_list_renderer.profile_details.profiles_formats,
            dataset_list_renderer.profile_details.available_profiles_dict,
        )
        return dataset_list_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        return dataset_list_renderer.render()


@alru_cache(maxsize=5)
@router.get("/dataset/{dataset_id}/collections", summary="List FeatureCollections")
async def feature_collections_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of SpacePrez geo:FeatureCollections in the necessary profile & mediatype"""
    dataset_id = request.path_params.get("dataset_id")  # can't be called by object ID

    collection_count, sparql_result = await asyncio.gather(
        count_collections(dataset_id),
        list_collections(dataset_id, page, per_page),
    )

    feature_collection_list = SpacePrezFeatureCollectionList(sparql_result)

    feature_collection_list_renderer = SpacePrezFeatureCollectionListRenderer(
        request,
        PREZ.FeatureCollectionList,
        page,
        per_page,
        int(collection_count[0]["count"]["value"]),
        feature_collection_list,
    )

    if feature_collection_list_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(feature_collection_list_renderer.instance_uri),
            feature_collection_list_renderer.profile_details.profiles_formats,
            feature_collection_list_renderer.profile_details.available_profiles_dict,
        )
        return feature_collection_list_renderer.render(
            alt_profiles_graph=alt_profiles_graph
        )
    else:
        return feature_collection_list_renderer.render()


@alru_cache(maxsize=5)
@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/items",
    summary="List Features",
)
async def features_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    # endpoint can't be called by object URI so safe to use dataset_id and collection_id from query params
    dataset_id = request.path_params.get("dataset_id")
    collection_id = request.path_params.get("collection_id")

    feature_count, sparql_result = await asyncio.gather(
        count_features(dataset_id, collection_id),
        list_features(dataset_id, collection_id, page, per_page),
    )

    feature_list = SpacePrezFeatureList(sparql_result)

    feature_list_renderer = SpacePrezFeatureListRenderer(
        request,
        PREZ.FeatureList,
        page,
        per_page,
        int(feature_count[0]["count"]["value"]),
        feature_list,
    )

    if feature_list_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(feature_list_renderer.instance_uri),
            feature_list_renderer.profile_details.profiles_formats,
            feature_list_renderer.profile_details.available_profiles_dict,
        )
        return feature_list_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        return feature_list_renderer.render()


@router.get("/dataset/{dataset_id}", summary="Get Dataset")
async def dataset_endpoint(request: Request):
    """Returns a SpacePrez dcat:Dataset in the necessary profile & mediatype"""
    return await dataset(request)


@alru_cache(maxsize=20)
async def dataset(
    request: Request,
):
    """Returns a SpacePrez dcat:Dataset in the necessary profile & mediatype"""
    dataset_renderer = SpacePrezDatasetRenderer(request)

    if dataset_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(dataset_renderer.instance_uri),
            dataset_renderer.profile_details.profiles_formats,
            dataset_renderer.profile_details.available_profiles_dict,
        )
        return dataset_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        sparql_result = await get_dataset_construct(
            dataset_id=dataset_renderer.dataset_id,
            dataset_uri=dataset_renderer.instance_uri,
        )
        if len(sparql_result) == 0:
            raise HTTPException(status_code=404, detail="Not Found")
        dataset = SpacePrezDataset(
            sparql_result,
            id=dataset_renderer.dataset_id,
            uri=dataset_renderer.instance_uri,
        )
        dataset_renderer.set_dataset(dataset)
        return dataset_renderer.render()


@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}",
    summary="Get FeatureCollections",
)
async def feature_collection_endpoint(request: Request):
    """Returns a SpacePrez geo:FeatureCollection in the necessary profile & mediatype"""
    return await feature_collection(request)


@alru_cache(maxsize=20)
async def feature_collection(request: Request):
    collection_renderer = SpacePrezFeatureCollectionRenderer(request)

    if collection_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(collection_renderer.instance_uri),
            collection_renderer.profile_details.profiles_formats,
            collection_renderer.profile_details.available_profiles_dict,
        )
        return collection_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        results = await asyncio.gather(
            get_collection_construct_1(
                dataset_id=collection_renderer.dataset_id,
                collection_id=collection_renderer.collection_id,
                collection_uri=collection_renderer.instance_uri,
            ),
            get_collection_construct_2(
                dataset_id=collection_renderer.dataset_id,
                collection_id=collection_renderer.collection_id,
                collection_uri=collection_renderer.instance_uri,
            ),
        )

        complete_feature_g = Graph()
        for g in results:
            complete_feature_g += g

        if len(complete_feature_g) == 0:
            raise HTTPException(status_code=404, detail="Not Found")

        collection = SpacePrezFeatureCollection(
            complete_feature_g,
            id=collection_renderer.collection_id,
            uri=collection_renderer.instance_uri,
            most_specific_class=collection_renderer.profile_details.most_specific_class,
        )

        collection_renderer.set_collection(collection)

        return collection_renderer.render()


@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/items/{feature_id}",
    summary="Get Feature",
)
async def feature_endpoint(
    request: Request, dataset_id: str, collection_id: str, feature_id: str
):
    """Returns a SpacePrez geo:Feature in the necessary profile & mediatype"""
    return await feature(request)


@alru_cache(maxsize=20)
async def feature(request: Request):
    feature_renderer = SpacePrezFeatureRenderer(request)

    if feature_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(feature_renderer.instance_uri),
            feature_renderer.profile_details.profiles_formats,
            feature_renderer.profile_details.available_profiles_dict,
        )
        return feature_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        complete_feature_g = get_feature_construct(feature_renderer.instance_uri)

        # retrieve relevant shapes
        feature_shapes_g = retrieve_relevant_shapes(
            feature_renderer.profile_details.profiles_g,
            feature_renderer.profile_details.available_profiles_dict[
                feature_renderer.profile
            ].uri,
            feature_renderer.profile_details.most_specific_class,
        )

        # filter out irrelevant properties:
        # for closed profiles; properties not specified in the profile
        # for open profiles; properties explicitly excluded in the profile (via dash:hidden)
        # TODO extend for open profiles (at the moment, for an open profile, everything is included, in future
        # open profiles should show everything except for specifically excluded properties
        if len(feature_shapes_g) > 0:
            complete_feature_g = apply_profile(complete_feature_g, feature_shapes_g)

        if len(complete_feature_g) == 0:
            raise HTTPException(status_code=404, detail="Not Found")

        feature = SpacePrezFeature(
            complete_feature_g + feature_shapes_g,
            id=feature_renderer.feature_id,
            uri=feature_renderer.instance_uri,
            most_specific_class=feature_renderer.profile_details.most_specific_class,
        )

        feature_renderer.set_feature(feature)

        return feature_renderer.render()


@router.get(
    "/spaceprez-about",
    summary="SpacePrez About",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def spaceprez_about(request: Request):
    """Returns the SpacePrez about page in the necessary profile & mediatype"""
    return templates.TemplateResponse(
        "spaceprez/spaceprez_about.html", {"request": request}
    )


@router.get(
    "/spaceprez-profiles",
    summary="SpacePrez Profiles",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def spaceprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by SpacePrez"""
    return await profiles_func(request, "SpacePrez")


@router.get("/conformance", summary="Conformance")
async def conformance(request: Request):
    """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
    conformance_renderer = SpacePrezConformanceRenderer(request)
    return conformance_renderer.render()
