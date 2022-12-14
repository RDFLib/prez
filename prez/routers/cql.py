from typing import Optional, List

from fastapi import APIRouter, Request
from fastapi import Form
from fastapi.responses import JSONResponse, RedirectResponse
from rdflib import Namespace
from prez.config import Settings

PREZ = Namespace("https://prez.dev/")

router = APIRouter(tags=["CQL"])

# # top-level features
# @router.get(
#     "/items",
#     summary="List Features",
# )
# async def spaceprez_features(
#     request: Request,
#     page: int = 1,
#     per_page: int = 20,
#     filter: Optional[str] = Query(None),
#     filter_lang: Optional[str] = Query(None, alias="filter-lang"),
#     filter_crs: Optional[str] = Query(None, alias="filter-crs"),
#     dataset: Optional[str] = Query(None),
#     collection: Optional[str] = Query(None),
# ):
#     """Returns a list of SpacePrez geo:Features in the necessary profile & mediatype"""
#     if filter is not None:
#         if dataset is None:
#             # get list of datasets
#             d_sparql_result = await list_datasets()
#             d_list = [result["id"]["value"] for result in d_sparql_result]
#             d_ids = ",".join(d_list)
#         else:
#             d_ids = dataset
#
#         if collection is None:
#             # get list of collections
#             coll_sparql_result, *_ = await asyncio.gather(
#                 *[list_collections(dataset_id) for dataset_id in d_list]
#             )
#             coll_list = [result["id"]["value"] for result in coll_sparql_result]
#             coll_ids = ",".join(coll_list)
#         else:
#             coll_ids = collection
#
#         # do CQL -> SPARQL mapping
#         cql_query = CQLSearch(
#             filter,
#             d_ids,
#             coll_ids,
#             filter_lang=filter_lang,
#             filter_crs=filter_crs,
#         ).generate_query()
#
#         feature_count, sparql_result = await asyncio.gather(
#             count_features(cql_query=cql_query),
#             list_features(cql_query=cql_query, page=page, per_page=per_page),
#         )
#     else:
#         feature_count, sparql_result = await asyncio.gather(
#             count_features(),
#             list_features(page=page, per_page=per_page),
#         )
#
#     feature_list = SpacePrezFeatureList(sparql_result)
#     feature_list_renderer = SpacePrezFeatureListRenderer(
#         request,
#         PREZ.FeatureList,
#         page,
#         per_page,
#         int(feature_count[0]["count"]["value"]),
#         feature_list,
#     )
#     return feature_list_renderer.render()


# top-level queryables
@router.get(
    "/queryables",
    summary="List available query parameters for CQL search globally",
)
async def queryables(
    request: Request,
):
    settings = Settings()

    """Returns a list of available properties to query against using CQL search globally"""
    content = {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "$id": f"{request.url.remove_query_params(keys=request.query_params.keys())}",
        "type": "object",
    }

    properties = {key: value for key, value in settings.cql_props.items()}
    for value in properties.values():
        value.pop("qname", None)

    content["properties"] = properties
    content["title"] = settings.spaceprez_title

    if settings.spaceprez_desc != "":
        content["description"] = settings.spaceprez_desc

    return JSONResponse(content=content)


# top-level CQL search form
@router.get(
    "/cql",
    summary="Endpoint to POST CQL search form data to",
)
async def cql(
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
