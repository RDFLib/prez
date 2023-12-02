from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import URIRef

from prez.dependencies import get_repo, cql_parser_dependency
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function_new
from prez.services.objects import object_function_new
from prez.sparql.methods import Repo

router = APIRouter(tags=["ogcrecords"])

ogc_endpoints = {
    "catalog-listing": "https://prez.dev/endpoint/ogcrecords/catalog-listing",
    "catalog-object": "https://prez.dev/endpoint/ogcrecords/catalog-object",
    "vocab-listing": "https://prez.dev/endpoint/ogcrecords/vocab-listing",
    "vocab-object": "https://prez.dev/endpoint/ogcrecords/vocab-object",
    "concept-listing": "https://prez.dev/endpoint/ogcrecords/concept-listing",
    "concept-object": "https://prez.dev/endpoint/ogcrecords/concept-object",
}


@router.get(
    "/catalogs",
    summary="List Catalogs",
    name=ogc_endpoints["catalog-listing"],
)
async def catalog_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    repo: Repo = Depends(get_repo),
):
    endpoint_uri = URIRef(ogc_endpoints["catalog-listing"])
    return await listing_function_new(request, repo, endpoint_uri, page, per_page)


@router.get(
    "/catalogs/{catalogId}/collections",
    summary="List Vocabularies",
    name=ogc_endpoints["vocab-listing"],
)
async def vocab_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    repo: Repo = Depends(get_repo),
):
    endpoint_uri = URIRef(ogc_endpoints["vocab-listing"])
    return await listing_function_new(request, repo, endpoint_uri, page, per_page)


@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items",
    summary="List Concepts",
    name=ogc_endpoints["concept-listing"],
)
async def vocab_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    repo: Repo = Depends(get_repo),
):
    endpoint_uri = URIRef(ogc_endpoints["concept-listing"])
    return await listing_function_new(request, repo, endpoint_uri, page, per_page)


@router.get(
    "/catalogs/{catalogId}",
    summary="Catalog Object",
    name=ogc_endpoints["catalog-object"],
)
async def catalog_object(
    request: Request,
    repo: Repo = Depends(get_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(ogc_endpoints["catalog-object"])
    object_uri = get_uri_for_curie_id(request.path_params["catalogId"])
    return await object_function_new(
        request, endpoint_uri, object_uri, request_url, repo
    )


@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}",
    summary="Vocab Object",
    name=ogc_endpoints["vocab-object"],
)
async def catalog_object(
    request: Request,
    repo: Repo = Depends(get_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(ogc_endpoints["vocab-object"])
    object_uri = get_uri_for_curie_id(request.path_params["collectionId"])
    return await object_function_new(
        request, endpoint_uri, object_uri, request_url, repo
    )


@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}",
    summary="Concept Object",
    name=ogc_endpoints["concept-object"],
)
async def catalog_object(
    request: Request,
    repo: Repo = Depends(get_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(ogc_endpoints["concept-object"])
    object_uri = get_uri_for_curie_id(request.path_params["itemId"])
    return await object_function_new(
        request, endpoint_uri, request_url, repo, object_uri
    )
