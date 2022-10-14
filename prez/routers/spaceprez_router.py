import io
from urllib.parse import quote_plus

from connegp import RDF_MEDIATYPES
from fastapi import APIRouter, Request
from fastapi import HTTPException, Query, Form
from fastapi.openapi.models import Response
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from rdflib import Namespace, URIRef

from prez.config import ENABLED_PREZS, SPACEPREZ_SPARQL_ENDPOINT
from prez.cql_search import CQLSearch
from prez.models.spaceprez import *
from prez.profiles.generate_profiles import (
    build_alt_graph,
)
from prez.renderers.spaceprez import *
from prez.services.spaceprez_service import *
from prez.services.spaceprez_service import get_object_uri_and_classes, sparql_construct
from prez.services.sparql_new import (
    generate_item_construct,
    get_labels,
    generate_listing_construct,
)
from prez.utils import templates
from prez.view_funcs import profiles_func
from prez.models.spaceprez.spaceprez_item import Item

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
async def list_items(request: Request, page: int = 1, per_page: int = 20):
    mediatype = "application/json"
    parent_item = Item(**request.path_params)
    profile, _ = connegp_placeholder(request, parent_item.general_class)
    query = generate_listing_construct(
        parent_item.children_general_class, parent_item.uri, page, per_page, profile
    )
    return await return_data(request, query, mediatype, profile, parent_item)


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
    mediatype = "text/html"
    item = Item(**request.path_params)
    profile, _ = connegp_placeholder(request, item.classes)
    query = generate_item_construct(item.uri, profile)  # profile will go here in future
    return await return_data(request, query, mediatype, profile, item)


async def return_data(request, query, mediatype, profile, item):
    if mediatype in RDF_MEDIATYPES:
        # return Response(graph.serialize(format=mediatype), media_type=mediatype)
        response = RedirectResponse(  # TODO confirm this is a valid response - not sure it will work outside browsers!
            url=SPACEPREZ_SPARQL_ENDPOINT + "?query=" + quote_plus(query),
            headers=request.headers,
        )
        return response
    else:  # all other responses require the RDF in memory
        _, graph = await sparql_construct(query, "SpacePrez")
        if mediatype == "text/html":
            labels_graph = await get_labels(graph)

            obj = io.BytesIO(
                (graph + labels_graph).serialize(format="json-ld", encoding="utf-8")
            )
            return StreamingResponse(content=obj, media_type="application/ld+json")
        elif mediatype == "application/json":
            # TODO complete - or move to frontend app
            if profile["uri"] == URIRef("https://w3id.org/profile/mem"):
                inner = {}
                for i, item_uri in enumerate(set(graph.subjects())):
                    inner[i] = {"uri": item_uri}
                    inner[i]["id"] = graph.value(
                        subject=item_uri, predicate=DCTERMS.identifier
                    )
                    inner[i]["title"] = graph.value(
                        subject=item_uri, predicate=DCTERMS.title
                    )
                    inner[i]["desc"] = graph.value(
                        subject=item_uri, predicate=DCTERMS.description
                    )
                    if item.children_general_class == GEO.FeatureCollection:
                        link = (
                            f"/dataset/{item.dataset_id}/collections/{inner[i]['id']}"
                        )
                    elif item.children_general_class == GEO.Feature:
                        link = f"/dataset/{item.dataset_id}/collections/{item.collection_id}/items/{inner[i]['id']}"
                    inner[i]["link"] = link
            outer = {"uri": str(request.url), "members": inner}
            return JSONResponse(content=outer)


def connegp_placeholder(request, classes):
    """placeholder function for connegp"""
    return (
        {"uri": URIRef("https://w3id.org/profile/mem"), "bnode_depth": 2},
        None,
    )
