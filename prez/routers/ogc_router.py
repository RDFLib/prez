from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import Namespace
from rdflib import URIRef

from prez.dependencies import get_repo, get_system_repo
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.repositories import Repo
from prez.reference_data.prez_ns import PREZ
from temp.grammar import IRI

router = APIRouter(tags=["ogccatprez"])

OGCE = Namespace(PREZ["endpoint/extended-ogc-records/"])


@router.get(
    "/catalogs",
    summary="Catalog Listing",
    name=OGCE["catalog-listing"],
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
        hierarchy_level=1,
        page=page,
        per_page=per_page,
        search_term=search_term,
    )


@router.get(
    "/catalogs/{catalogId}/collections",
    summary="Collection Listing",
    name=OGCE["collection-listing"],
)
async def collection_listing(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    search_term: Optional[str] = None,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    search_term = request.query_params.get("q")

    path_node_1_uri = get_uri_for_curie_id(request.path_params["catalogId"])
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request,
        repo,
        system_repo,
        endpoint_uri,
        hierarchy_level=2,
        path_nodes={"path_node_1": IRI(value=path_node_1_uri)},
        page=page,
        per_page=per_page,
        parent_uri=path_node_1_uri,
        search_term=search_term,
    )


@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items",
    summary="Item Listing",
    name=OGCE["item-listing"],
)
async def item_listing(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    search_term: Optional[str] = None,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    search_term = request.query_params.get("q")
    path_node_1_uri = get_uri_for_curie_id(request.path_params["collectionId"])
    path_node_2_uri = get_uri_for_curie_id(request.path_params["catalogId"])
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request,
        repo,
        system_repo,
        endpoint_uri,
        hierarchy_level=3,
        path_nodes={
            "path_node_1": IRI(value=path_node_1_uri),
            "path_node_2": IRI(value=path_node_2_uri),
        },
        page=page,
        per_page=per_page,
        parent_uri=path_node_1_uri,
        search_term=search_term,
    )


@router.get(
    "/catalogs/{catalogId}",
    summary="Catalog Object",
    name=OGCE["catalog-object"],
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
    summary="Collection Object",
    name=OGCE["collection-object"],
)
async def collection_object(
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
    summary="Item Object",
    name=OGCE["item-object"],
)
async def item_object(
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
