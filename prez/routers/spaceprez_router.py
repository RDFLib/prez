from fastapi import APIRouter, Request, HTTPException, Query, Form
from fastapi.responses import JSONResponse, RedirectResponse
import asyncio

from prez.models.spaceprez import *
from prez.profiles.generate_profiles import (
    ProfileDetails,
    get_general_profiles,
    get_class_based_and_default_profiles,
    retrieve_relevant_shapes,
    build_alt_graph,
    apply_profile,
)
from prez.renderers.spaceprez import *
from prez.services.spaceprez_service import *
from prez.utils import templates
from prez.view_funcs import profiles_func
from prez.config import *
from prez.cql_search import CQLSearch

PREZ = Namespace("https://surroundaustralia.com/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


@alru_cache(maxsize=20)
async def home(request: Request):
    profile_details = ProfileDetails(
        general_class=PREZ.HomePage, item_uri=PREZ.HomePage
    )
    await profile_details.get_all_profiles("SpacePrez")

    home_renderer = SpacePrezHomeRenderer(
        request,
        profile_details.available_profiles_dict,
        profile_details.default_profile,
        PREZ.HomePage,
    )

    if home_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            PREZ.HomePage,
            profile_details.profiles_formats,
            profile_details.available_profiles_dict,
        )
        return home_renderer.render(alt_profiles_graph=alt_profiles_graph)

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
    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(
        general_class=PREZ.DatasetList, item_uri=instance_uri
    )
    await profile_details.get_all_profiles("SpacePrez")

    dataset_count, sparql_result = await asyncio.gather(
        count_datasets(), list_datasets(page, per_page)
    )
    dataset_list = SpacePrezDatasetList(sparql_result)
    dataset_list_renderer = SpacePrezDatasetListRenderer(
        request,
        instance_uri,
        "Dataset list",
        "A list of dcat:Datasets",
        dataset_list,
        page,
        per_page,
        int(dataset_count[0]["count"]["value"]),
        profile_details.available_profiles_dict,
        profile_details.default_profile,
    )

    if dataset_list_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(instance_uri),
            profile_details.profiles_formats,
            profile_details.available_profiles_dict,
        )
        return dataset_list_renderer.render(alt_profiles_graph=alt_profiles_graph)

    return dataset_list_renderer.render()


@router.get("/dataset/{dataset_id}", summary="Get Dataset")
async def dataset(request: Request, dataset_id: str):
    """Returns a SpacePrez dcat:Dataset in the necessary profile & mediatype"""
    return await dataset_endpoint(request, dataset_id=dataset_id)


@alru_cache(maxsize=20)
async def dataset_endpoint(
    request: Request,
    dataset_id: Optional[str] = None,
    dataset_uri: Optional[str] = None,
):
    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(general_class=DCAT.Dataset, item_uri=instance_uri)
    await profile_details.get_all_profiles("SpacePrez")

    if not dataset_uri:
        dataset_uri = await get_uri(dataset_id, URIRef(DCAT.Dataset))

    dataset_renderer = SpacePrezDatasetRenderer(
        request,
        profile_details.available_profiles_dict,
        profile_details.default_profile,
        dataset_uri,
    )

    profile = dataset_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(dataset_uri),
            profile_details.profiles_formats,
            profile_details.available_profiles_dict,
        )
        return dataset_renderer.render(alt_profiles_graph=alt_profiles_graph)

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
    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(
        general_class=PREZ.FeatureCollectionList, item_uri=instance_uri
    )
    await profile_details.get_all_profiles("SpacePrez")

    collection_count, sparql_result = await asyncio.gather(
        count_collections(dataset_id),
        list_collections(dataset_id, page, per_page),
    )
    feature_collection_list = SpacePrezFeatureCollectionList(sparql_result)
    feature_collection_list_renderer = SpacePrezFeatureCollectionListRenderer(
        request,
        profile_details.available_profiles_dict,
        profile_details.default_profile,
        instance_uri,
        "FeatureCollection list",
        "A list of geo:FeatureCollections",
        feature_collection_list,
        page,
        per_page,
        int(collection_count[0]["count"]["value"]),
    )

    profile = feature_collection_list_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(instance_uri),
            profile_details.profiles_formats,
            profile_details.available_profiles_dict,
        )
        return feature_collection_list_renderer.render(
            alt_profiles_graph=alt_profiles_graph
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


@alru_cache(maxsize=20)
async def feature_collection_endpoint(
    request: Request,
    dataset_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
):
    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(
        general_class=GEO.FeatureCollection, item_uri=instance_uri
    )
    await profile_details.get_all_profiles("SpacePrez")

    collection_renderer = SpacePrezFeatureCollectionRenderer(
        request,
        profile_details.available_profiles_dict,
        profile_details.default_profile,
        instance_uri,
    )

    profile = collection_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(instance_uri),
            profile_details.profiles_formats,
            profile_details.available_profiles_dict,
        )
        return collection_renderer.render(alt_profiles_graph=alt_profiles_graph)

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
@alru_cache(maxsize=20)
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
    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(
        general_class=PREZ.FeatureList, item_uri=instance_uri
    )
    await profile_details.get_all_profiles("SpacePrez")

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

        feature_count, sparql_result, dataset_title_result, collection_title_result = await asyncio.gather(
            count_features(dataset_id=dataset_id, collection_id=collection_id, cql_query=cql_query),
            list_features(dataset_id=dataset_id, collection_id=collection_id, page=page, per_page=per_page, cql_query=cql_query),
            get_dataset_label(dataset_id=dataset_id),
            get_collection_label(collection_id=collection_id)
        )
    else:
        feature_count, sparql_result, dataset_title_result, collection_title_result = await asyncio.gather(
            count_features(dataset_id=dataset_id, collection_id=collection_id),
            list_features(dataset_id=dataset_id, collection_id=collection_id, page=page, per_page=per_page),
            get_dataset_label(dataset_id=dataset_id),
            get_collection_label(collection_id=collection_id)
        )
    
    d = {
        "id": dataset_id,
        "title": dataset_title_result[0]["title"]["value"]
    }
    coll = {
        "id": collection_id,
        "title": collection_title_result[0]["title"]["value"]
    }

    feature_list = SpacePrezFeatureList(sparql_result, dataset=d, collection=coll)
    feature_list_renderer = SpacePrezFeatureListRenderer(
        request,
        profile_details.available_profiles_dict,
        profile_details.default_profile,
        instance_uri,
        "Feature list",
        f"A list of {feature_list.collection['title']}",
        feature_list,
        page,
        per_page,
        int(feature_count[0]["count"]["value"]),
    )

    profile = feature_list_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(instance_uri),
            profile_details.profiles_formats,
            profile_details.available_profiles_dict,
        )
        return feature_list_renderer.render(alt_profiles_graph=alt_profiles_graph)

    return feature_list_renderer.render()


@alru_cache(maxsize=20)
async def feature_endpoint(
    request: Request,
    dataset_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    feature_uri: Optional[str] = None,
):
    feature_id, feature_uri, feature_classes = await get_feature_uri_and_classes(
        feature_id, feature_uri, collection_id, dataset_id
    )

    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(general_class=GEO.Feature, item_uri=instance_uri)
    await profile_details.get_all_profiles("SpacePrez")

    # find the most specific class for the feature
    for klass, _, distance in profile_details.preferred_classes_and_profiles:
        if klass in feature_classes:
            most_specific_class = klass
            break

    feature_renderer = SpacePrezFeatureRenderer(
        request,
        feature_uri,
        available_profiles=profile_details.available_profiles_dict,
        default_profile=profile_details.default_profile,
    )
    profile = feature_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(feature_uri),
            profile_details.profiles_formats,
            profile_details.available_profiles_dict,
        )
        return feature_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        complete_feature_g = await get_feature_construct(
            dataset_id=dataset_id,
            collection_id=collection_id,
            feature_id=feature_id,
            feature_uri=feature_uri,
        )

        # retrieve relevant shapes
        feature_shapes_g = await retrieve_relevant_shapes(
            profile_details.profiles_g,
            profile_details.available_profiles_dict[profile].uri,
            most_specific_class,
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
            id=feature_id,
            uri=feature_uri,
            most_specific_class=most_specific_class,
        )

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
@alru_cache(maxsize=20)
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
    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(
        general_class=PREZ.Conformance, item_uri=instance_uri
    )
    await profile_details.get_all_profiles("SpacePrez")

    conformance_renderer = SpacePrezConformanceRenderer(
        request,
        profile_details.available_profiles_dict,
        profile_details.default_profile,
        instance_uri,
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

# dataset features
@router.get(
    "/dataset/{dataset_id}/items",
    summary="List Features",
)
async def dataset_features(
    request: Request,
    dataset_id: str,
    page: int = 1,
    per_page: int = 20,
    filter: Optional[str] = Query(None),
    filter_lang: Optional[str] = Query(None, alias="filter-lang"),
    filter_crs: Optional[str] = Query(None, alias="filter-crs"),
    collection: Optional[str] = Query(None)
):
    """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
    if filter is not None:
        if collection is None:
            # get list of collections
            coll_sparql_result = await list_collections(dataset_id)
            coll_list = [result["id"]["value"] for result in coll_sparql_result]
            coll_ids = ",".join(coll_list)
        else:
            coll_ids = collection

        # do CQL -> SPARQL mapping
        cql_query = CQLSearch(
            filter,
            dataset_id,
            coll_ids,
            filter_lang=filter_lang,
            filter_crs=filter_crs,
        ).generate_query()

        feature_count, sparql_result, dataset_title_result = await asyncio.gather(
            count_features(dataset_id=dataset_id, cql_query=cql_query),
            list_features(dataset_id=dataset_id, cql_query=cql_query, page=page, per_page=per_page),
            get_dataset_label(dataset_id=dataset_id)
        )
    else:
        feature_count, sparql_result, dataset_title_result = await asyncio.gather(
            count_features(dataset_id=dataset_id),
            list_features(dataset_id=dataset_id, page=page, per_page=per_page),
            get_dataset_label(dataset_id=dataset_id)
        )
    
    d = {
        "id": dataset_id,
        "title": dataset_title_result[0]["title"]["value"]
    }

    feature_list = SpacePrezFeatureList(sparql_result, dataset=d)
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

# dataset queryables
@router.get(
    "/dataset/{dataset_id}/queryables",
    summary="List available query parameters for CQL search on a Dataset",
)
async def dataset_queryables(
    request: Request, dataset_id: str,
):
    """Returns a list of available properties to query against using CQL search for a specific dcat:Dataset"""
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
    sparql_result = await get_dataset_info_queryables(
        dataset_id=dataset_id, dataset_uri=None
    )

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")

    content["title"] = sparql_result[0]["title"]["value"]

    if sparql_result[0].get("desc") is not None:
        content["description"] = sparql_result[0]["desc"]["value"]

    return JSONResponse(content=content)

# dataset CQL search form
@router.post(
    "/dataset/{dataset_id}/cql",
    summary="Endpoint to POST CQL search form data to",
)
async def dataset_cql(
    request: Request,
    dataset_id: str,
    title: Optional[str] = Form(None),
    desc: Optional[str] = Form(None),
    filter: Optional[str] = Form(None),
    collections: Optional[List[str]] = Form(None),
):
    """Handles form data from a CQL search form & redirects to /items containing the filter param"""
    filter_params = []
    if title is not None:
        filter_params.append(f'title LIKE "{title}"')
    if desc is not None:
        filter_params.append(f'desc LIKE "{desc}"')
    if filter is not None:
        filter_params.append(filter)
    if collections is not None:
        coll_set = set()
        for coll in collections:
            if "," in coll:
                coll_set.update(coll.split(","))
            else:
                coll_set.add(coll)

    return RedirectResponse(
        url=f'/dataset/{dataset_id}/items?filter={" AND ".join(filter_params)}{"&collection=" + ",".join(coll_set) if collections is not None else ""}',
        status_code=302,
    )

# top-level features
@router.get(
    "/items",
    summary="List Features",
)
async def spaceprez_features(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    filter: Optional[str] = Query(None),
    filter_lang: Optional[str] = Query(None, alias="filter-lang"),
    filter_crs: Optional[str] = Query(None, alias="filter-crs"),
):
    """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
    if filter is not None:
        # get list of datasets
        d_sparql_result = await list_datasets(page, per_page)
        d_list = [result["id"]["value"] for result in d_sparql_result]
        
        # get list of collections
        coll_sparql_result, *_ = await asyncio.gather(*[list_collections(dataset_id) for dataset_id in d_list])
        coll_list = [result["id"]["value"] for result in coll_sparql_result]

        # do CQL -> SPARQL mapping
        cql_query = CQLSearch(
            filter,
            ",".join(d_list),
            ",".join(coll_list),
            filter_lang=filter_lang,
            filter_crs=filter_crs,
        ).generate_query()

        feature_count, sparql_result = await asyncio.gather(
            count_features(cql_query=cql_query),
            list_features(cql_query=cql_query, page=page, per_page=per_page),
        )
    else:
        feature_count, sparql_result = await asyncio.gather(
            count_features(),
            list_features(page=page, per_page=per_page),
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

# top-level queryables
@router.get(
    "/queryables",
    summary="List available query parameters for CQL search globally",
)
async def dataset_queryables(
    request: Request,
):
    """Returns a list of available properties to query against using CQL search globally"""
    content = {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$id": f"{request.url.remove_query_params(keys=request.query_params.keys())}",
        "type": "object",
    }

    properties = {key: value for key, value in CQL_PROPS.items()}
    for value in properties.values():
        value.pop("qname", None)
    
    content["properties"] = properties
    content["title"] = SPACEPREZ_TITLE

    if SPACEPREZ_DESC != "":
        content["description"] = SPACEPREZ_DESC

    return JSONResponse(content=content)

# top-level CQL search form
@router.post(
    "/cql",
    summary="Endpoint to POST CQL search form data to",
)
async def spaceprez_cql(
    request: Request,
    title: Optional[str] = Form(None),
    desc: Optional[str] = Form(None),
    filter: Optional[str] = Form(None),
    datasets: Optional[List[str]] = Form(None),
    collections: Optional[List[str]] = Form(None),
):
    """Handles form data from a CQL search form & redirects to /items containing the filter param"""
    filter_params = []
    if title is not None:
        filter_params.append(f'title LIKE "{title}"')
    if desc is not None:
        filter_params.append(f'desc LIKE "{desc}"')
    if filter is not None:
        filter_params.append(filter)
    if datasets is not None:
        d_set = set()
        for d in datasets:
            if "," in d:
                d_set.update(d.split(","))
            else:
                d_set.add(d)
    if collections is not None:
        coll_set = set()
        for coll in collections:
            if "," in coll:
                coll_set.update(coll.split(","))
            else:
                coll_set.add(coll)
    return RedirectResponse(
        url=f'/items?filter={" AND ".join(filter_params)}{"&dataset=" + ",".join(d_set) if datasets is not None else ""}{"&collection=" + ",".join(coll_set) if collections is not None else ""}',
        status_code=302,
    )
