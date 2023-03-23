from typing import Optional, List

from fastapi import APIRouter, Request
from fastapi import Form
from fastapi.responses import JSONResponse, RedirectResponse
from rdflib import Namespace
from prez.config import Settings

PREZ = Namespace("https://prez.dev/")

router = APIRouter(tags=["CQL"])


# # CQL search_methods
# if "SpacePrez" in settings.ENABLED_PREZS:
#     dataset_sparql_result, collection_sparql_result = await asyncio.gather(
#         list_datasets(),
#         list_collections(),
#     )
#     datasets = [
#         {"id": result["id"]["value"], "title": result["label"]["value"]}
#         for result in dataset_sparql_result
#     ]
#     collections = [
#         {"id": result["id"]["value"], "title": result["label"]["value"]}
#         for result in collection_sparql_result
#     ]
# return

# top-level queryables
@router.get(
    "/queryables",
    summary="List available query parameters for CQL search_methods globally",
)
async def queryables(
    request: Request,
):
    settings = Settings()

    """Returns a list of available properties to query against using CQL search_methods globally"""
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


# top-level CQL search_methods form
@router.get(
    "/cql",
    summary="Endpoint to POST CQL search_methods form data to",
)
async def cql(
    request: Request,
    title: Optional[str] = Form(None),
    desc: Optional[str] = Form(None),
    filter: Optional[str] = Form(None),
    datasets: Optional[List[str]] = Form(None),
    collections: Optional[List[str]] = Form(None),
):
    """Handles form data from a CQL search_methods form & redirects to /items containing the filter param"""
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
