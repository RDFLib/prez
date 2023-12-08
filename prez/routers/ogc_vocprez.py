from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import PlainTextResponse
from rdflib import URIRef

from prez.dependencies import get_repo, get_system_repo
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.sparql.methods import Repo

router = APIRouter(tags=["ogcvocprez"])

ogc_endpoints = {
    "catalog-listing": "https://prez.dev/endpoint/ogcvocprez/catalog-listing",
    "catalog-object": "https://prez.dev/endpoint/ogcvocprez/catalog-object",
    "vocab-listing": "https://prez.dev/endpoint/ogcvocprez/vocab-listing",
    "vocab-object": "https://prez.dev/endpoint/ogcvocprez/vocab-object",
    "concept-listing": "https://prez.dev/endpoint/ogcvocprez/concept-listing",
    "concept-object": "https://prez.dev/endpoint/ogcvocprez/concept-object",
    "top-concepts": "https://prez.dev/endpoint/ogcvocprez/top-concepts",
    "narrowers": "https://prez.dev/endpoint/ogcvocprez/narrowers",
}


@router.get(
    "/v/catalogs",
    summary="List Catalogs",
    name=ogc_endpoints["catalog-listing"],
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
    "/v/catalogs/{catalogId}/collections",
    summary="List Vocabularies",
    name=ogc_endpoints["vocab-listing"],
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
    "/v/catalogs/{catalogId}/collections/{collectionId}/items",
    summary="List Concepts",
    name=ogc_endpoints["concept-listing"],
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
    "/v/catalogs/{catalogId}/collections/{collectionId}/top-concepts",
    summary="List Top Concepts",
    name=ogc_endpoints["top-concepts"],
)
async def top_concepts(
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


@router.get("/v", summary="VocPrez Home")
async def vocprez_home():
    return PlainTextResponse("VocPrez Home")


@router.get(
    "/v/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}/narrowers",
    summary="List Narrower Concepts",
    name=ogc_endpoints["narrowers"],
)
async def narrowers(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    search_term: Optional[str] = None,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    search_term = request.query_params.get("q")
    parent_uri = get_uri_for_curie_id(request.path_params["itemId"])
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
    "/v/catalogs/{catalogId}",
    summary="Catalog Object",
    name=ogc_endpoints["catalog-object"],
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
    "/v/catalogs/{catalogId}/collections/{collectionId}",
    summary="Vocab Object",
    name=ogc_endpoints["vocab-object"],
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
    "/v/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}",
    summary="Concept Object",
    name=ogc_endpoints["concept-object"],
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
