import io

from fastapi import APIRouter, Request
from fastapi import HTTPException, Query, Form
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from prez.cql_search import CQLSearch
from prez.renderers.spaceprez import *
from prez.services.spaceprez_service import *
from prez.services.spaceprez_service import sparql_construct
from prez.services.sparql_new import (
    generate_item_construct,
    get_annotation_properties,
    generate_listing_construct,
)
from prez.utils import templates
from prez.view_funcs import profiles_func
from prez.models.spaceprez_item import SpatialItem
from prez.cache import tbox_cache, missing_annotations

PREZ = Namespace("https://kurrawong.net/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


@alru_cache(maxsize=5)
@router.get(
    "/spaceprez", summary="SpacePrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def spaceprez_home_endpoint(request: Request):
    """Returns the SpacePrez home page in the necessary profile & mediatype"""

    return SpacePrezHomeRenderer(request)._render_oai_json()
    # # if home_renderer.profile == "alt":
    # alt_profiles_graph = await build_alt_graph(
    #     PREZ.SpacePrezHome,
    #     home_renderer.profile_details.profiles_formats,
    #     home_renderer.profile_details.available_profiles_dict,
    # )
    # obj = io.BytesIO(alt_profiles_graph.serialize(format="json-ld", encoding="utf-8"))
    # return StreamingResponse(obj, media_type="application/ld+json")
    #     return home_renderer.render(alt_profiles_graph=alt_profiles_graph)
    # return home_renderer.render()


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
    collection: Optional[str] = Query(None),
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
            list_features(
                dataset_id=dataset_id, cql_query=cql_query, page=page, per_page=per_page
            ),
            get_dataset_label(dataset_id=dataset_id),
        )
    else:
        feature_count, sparql_result, dataset_title_result = await asyncio.gather(
            count_features(dataset_id=dataset_id),
            list_features(dataset_id=dataset_id, page=page, per_page=per_page),
            get_dataset_label(dataset_id=dataset_id),
        )

    d = {"id": dataset_id, "title": dataset_title_result[0]["title"]["value"]}

    feature_list = SpacePrezFeatureList(sparql_result, dataset=d)
    feature_list_renderer = SpacePrezFeatureListRenderer(
        request,
        PREZ.FeatureList,
        page,
        per_page,
        int(feature_count[0]["count"]["value"]),
        feature_list,
    )
    return feature_list_renderer.render()


# dataset queryables
@router.get(
    "/dataset/{dataset_id}/queryables",
    summary="List available query parameters for CQL search on a Dataset",
)
async def dataset_queryables(
    request: Request,
    dataset_id: str,
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
    dataset: Optional[str] = Query(None),
    collection: Optional[str] = Query(None),
):
    """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
    if filter is not None:
        if dataset is None:
            # get list of datasets
            d_sparql_result = await list_datasets()
            d_list = [result["id"]["value"] for result in d_sparql_result]
            d_ids = ",".join(d_list)
        else:
            d_ids = dataset

        if collection is None:
            # get list of collections
            coll_sparql_result, *_ = await asyncio.gather(
                *[list_collections(dataset_id) for dataset_id in d_list]
            )
            coll_list = [result["id"]["value"] for result in coll_sparql_result]
            coll_ids = ",".join(coll_list)
        else:
            coll_ids = collection

        # do CQL -> SPARQL mapping
        cql_query = CQLSearch(
            filter,
            d_ids,
            coll_ids,
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
        PREZ.FeatureList,
        page,
        per_page,
        int(feature_count[0]["count"]["value"]),
        feature_list,
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


@router.get("/datasets", summary="List Datasets")
async def list_items(
    request: Request, page: Optional[int] = 1, per_page: Optional[int] = 20
):
    """Returns a list of SpacePrez datasets in the requested profile & mediatype"""
    general_item = SpatialItem(**request.path_params)
    profile, mediatype = connegp_placeholder(
        request, general_item.children_general_class
    )
    query = generate_listing_construct(general_item, page, per_page, profile)
    return await return_data(query, mediatype, profile, "SpacePrez")


@router.get(
    "/dataset/{dataset_id}/collections",
    summary="List Feature Collections",
)
async def list_items_feature_collections(
    request: Request, dataset_id: str, page: int = 1, per_page: int = 20
):
    return await list_items(request, page, per_page)


@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/items",
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


@router.get("/dataset/{dataset_id}", summary="Get Dataset")
async def dataset_item(request: Request, dataset_id: str):
    return await item_endpoint(request)


@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}",
    summary="Get Feature Collection",
)
async def dataset_item(request: Request, dataset_id: str, collection_id: str):
    return await item_endpoint(request)


@router.get(
    "/dataset/{dataset_id}/collections/{collection_id}/items/{feature_id}",
    summary="Get Feature",
)
async def dataset_item(
    request: Request, dataset_id: str, collection_id: str, feature_id: str
):
    return await item_endpoint(request)


async def item_endpoint(request: Request):
    item = SpatialItem(**request.path_params, url=request.url)
    profile, mediatype = connegp_placeholder(request, item.classes)
    query = generate_item_construct(item, profile)
    return await return_data(query, mediatype, profile, "SpacePrez")


async def return_data(query_or_queries, mediatype, profile, prez):
    cache_ref = tbox_cache
    if isinstance(query_or_queries, list):
        results = await asyncio.gather(
            *[sparql_construct(query, prez) for query in query_or_queries]
        )
        graph = Graph()
        for result in results:
            graph += result[1]
    else:
        _, graph = await sparql_construct(query_or_queries, prez)
    if mediatype in RDF_MEDIATYPES:
        obj = io.BytesIO(graph.serialize(format=mediatype, encoding="utf-8"))
        return StreamingResponse(content=obj, media_type=mediatype)
    else:  # all other responses require the RDF in memory
        if mediatype == "text/html":
            queries_for_uncached, labels_graph = await get_annotation_properties(graph)
            results = await sparql_construct(queries_for_uncached, prez)
            # results = await asyncio.gather(
            #     *[sparql_construct(query, prez) for query in queries_for_uncached]
            # )
            # for i, r in enumerate(results):
            if results[1]:
                labels_graph += results[1]
                cache_ref += results[1]
                # else:
                #     missing_annotations.append(queries_for_uncached[i])
            obj = io.BytesIO(
                (graph + labels_graph).serialize(format="turtle", encoding="utf-8")
            )
            return StreamingResponse(content=obj, media_type="text/turtle")


def connegp_placeholder(request, classes):
    """placeholder function for connegp"""
    return (
        {
            "uri": URIRef("https://w3id.org/profile/mem"),
            "bnode_depth": 2,
        },
        "text/html",
    )
