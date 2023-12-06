from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import URIRef

from prez.dependencies import get_repo, cql_parser_dependency, get_system_repo
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function_new
from prez.services.objects import object_function_new
from prez.sparql.methods import Repo

router = APIRouter(tags=["ogccatprez"])

ogc_endpoints = {
    "top-level-catalog-listing": "https://prez.dev/endpoint/ogccatprez/top-level-catalog-listing",
    "top-level-catalog-object": "https://prez.dev/endpoint/ogccatprez/top-level-catalog-object",
    "lower-level-catalog-listing": "https://prez.dev/endpoint/ogccatprez/lower-level-catalog-listing",
    "lower-level-catalog-object": "https://prez.dev/endpoint/ogccatprez/lower-level-catalog-object",
    "resource-listing": "https://prez.dev/endpoint/ogccatprez/resource-listing",
    "resource-object": "https://prez.dev/endpoint/ogccatprez/resource-object",
}


@router.get(
    "/c/catalogs",
    summary="List Top Level Catalogs",
    name=ogc_endpoints["top-level-catalog-listing"],
)
async def catalog_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function_new(
        request, repo, system_repo, endpoint_uri, page, per_page
    )


@router.get(
    "/c/catalogs/{catalogId}/collections",
    summary="List Lower Level Catalogs",
    name=ogc_endpoints["lower-level-catalog-listing"],
)
async def vocab_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    parent_uri = get_uri_for_curie_id(request.path_params["catalogId"])
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function_new(
        request, repo, system_repo, endpoint_uri, page, per_page, parent_uri
    )


@router.get(
    "/c/catalogs/{catalogId}/collections/{collectionId}/items",
    summary="List Resources",
    name=ogc_endpoints["resource-listing"],
)
async def concept_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    parent_uri = get_uri_for_curie_id(request.path_params["collectionId"])
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function_new(
        request, repo, system_repo, endpoint_uri, page, per_page, parent_uri
    )


@router.get(
    "/c/catalogs/{catalogId}",
    summary="Top Level Catalog Object",
    name=ogc_endpoints["top-level-catalog-object"],
)
async def catalog_object(
    request: Request,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(request.scope.get("route").name)
    object_uri = get_uri_for_curie_id(request.path_params["catalogId"])
    return await object_function_new(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )


@router.get(
    "/c/catalogs/{catalogId}/collections/{collectionId}",
    summary="Lower Level Catalog Object",
    name=ogc_endpoints["lower-level-catalog-object"],
)
async def catalog_object(
    request: Request,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(request.scope.get("route").name)
    object_uri = get_uri_for_curie_id(request.path_params["collectionId"])
    return await object_function_new(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )


@router.get(
    "/c/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}",
    summary="Resource Object",
    name=ogc_endpoints["resource-object"],
)
async def catalog_object(
    request: Request,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(request.scope.get("route").name)
    object_uri = get_uri_for_curie_id(request.path_params["itemId"])
    return await object_function_new(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )
