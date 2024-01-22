from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import Namespace
from rdflib import URIRef

from prez.dependencies import get_repo, get_system_repo
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.sparql.methods import Repo
from prez.reference_data.prez_ns import PREZ

router = APIRouter(tags=["ogccatprez"])

OGCE = Namespace(PREZ["endpoint/extended-ogc-records/"])

ogc_endpoints = {
    "top-level-catalog-listing": OGCE["top-level-catalog-listing"],
    "top-level-catalog-object": OGCE["top-level-catalog-object"],
    "lower-level-catalog-listing": OGCE["lower-level-catalog-listing"],
    "lower-level-catalog-object": OGCE["lower-level-catalog-object"],
    "resource-listing": OGCE["resource-listing"],
    "resource-object": OGCE["resource-object"],
}


@router.get(
    "/catalogs",
    summary="List Top Level Catalogs",
    name=ogc_endpoints["top-level-catalog-listing"],
)
async def catalog_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    search_term: Optional[str] = None,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    search_term = request.query_params.get("q")
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request,
        repo,
        system_repo,
        endpoint_uri,
        page,
        per_page,
        search_term=search_term,
    )


@router.get(
    "/catalogs/{catalogId}/collections",
    summary="List Lower Level Catalogs",
    name=ogc_endpoints["lower-level-catalog-listing"],
)
async def vocab_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    search_term: Optional[str] = None,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    search_term = request.query_params.get("q")

    parent_uri = get_uri_for_curie_id(request.path_params["catalogId"])
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request,
        repo,
        system_repo,
        endpoint_uri,
        page,
        per_page,
        parent_uri,
        search_term=search_term,
    )


@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items",
    summary="List Resources",
    name=ogc_endpoints["resource-listing"],
)
async def concept_list(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    search_term: Optional[str] = None,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    search_term = request.query_params.get("q")
    parent_uri = get_uri_for_curie_id(request.path_params["collectionId"])
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request,
        repo,
        system_repo,
        endpoint_uri,
        page,
        per_page,
        parent_uri,
        search_term=search_term,
    )


@router.get(
    "/catalogs/{catalogId}",
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
    return await object_function(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )


@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}",
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
    return await object_function(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )


@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}",
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
    return await object_function(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )
