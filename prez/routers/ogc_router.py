from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import Namespace
from rdflib import URIRef

from prez.dependencies import get_data_repo, get_system_repo, generate_search_query, cql_get_parser_dependency, \
    get_endpoint_nodeshapes, get_negotiated_pmts, get_profile_nodeshape, get_endpoint_structure
from prez.reference_data.prez_ns import PREZ, EP
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function_new
from prez.services.objects import object_function, object_function_new
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape
from temp.grammar import IRI, ConstructQuery

router = APIRouter(tags=["ogccatprez"])

OGCE = Namespace(PREZ["endpoint/extended-ogc-records/"])


@router.get(
    "/profiles",
    summary="List Profiles",
    name=EP["system/profile-listing"],
)
@router.get(
    "/catalogs",
    summary="Catalog Listing",
    name=OGCE["catalog-listing"],
)
@router.get(
    "/catalogs/{catalogId}/collections",
    summary="Collection Listing",
    name=OGCE["collection-listing"],
)
@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items",
    summary="Item Listing",
    name=OGCE["item-listing"],
)
async def listings(
        page: Optional[int] = 1,
        per_page: Optional[int] = 20,
        order_by: Optional[str] = None,
        order_by_direction: Optional[str] = None,
        endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
        pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
        endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure),
        profile_nodeshape: NodeShape = Depends(get_profile_nodeshape),
        cql_parser: CQLParser = Depends(cql_get_parser_dependency),
        search_query: ConstructQuery = Depends(generate_search_query),
        data_repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    return await listing_function_new(
        data_repo=data_repo,
        system_repo=system_repo,
        endpoint_nodeshape=endpoint_nodeshape,
        endpoint_structure=endpoint_structure,
        search_query=search_query,
        cql_parser=cql_parser,
        pmts=pmts,
        profile_nodeshape=profile_nodeshape,
        page=page,
        per_page=per_page,
        order_by=order_by,
        order_by_direction=order_by_direction,
    )


########################################################################################################################
# Object endpoints
########################################################################################################################

@router.get(
    "/profiles/{profile_curie}",
    summary="Profile",
    name=EP["system/profile-object"],
)
@router.get(
    "/catalogs/{catalogId}",
    summary="Catalog Object",
    name=OGCE["catalog-object"],
)
@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}",
    summary="Collection Object",
    name=OGCE["collection-object"],
)
@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}",
    summary="Item Object",
    name=OGCE["item-object"],
)
async def objects(
        pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
        endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure),
        profile_nodeshape: NodeShape = Depends(get_profile_nodeshape),
        data_repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    return await object_function_new(
        data_repo=data_repo,
        system_repo=system_repo,
        endpoint_structure=endpoint_structure,
        pmts=pmts,
        profile_nodeshape=profile_nodeshape,
    )


# async def collection_listing(
#     request: Request,
#     page: Optional[int] = 1,
#     per_page: Optional[int] = 20,
#     search_term: Optional[str] = None,
#     repo: Repo = Depends(get_repo),
#     system_repo: Repo = Depends(get_system_repo),
# ):
#     search_term = request.query_params.get("q")
#
#     path_node_1_uri = await get_uri_for_curie_id(request.path_params["catalogId"])
#     endpoint_uri = URIRef(request.scope.get("route").name)
#     return await listing_function(
#         request,
#         repo,
#         system_repo,
#         endpoint_uri,
#         hierarchy_level=2,
#         path_nodes={"path_node_1": IRI(value=path_node_1_uri)},
#         page=page,
#         per_page=per_page,
#         search_term=search_term,
#     )
#
#
#
# async def item_listing(
#     request: Request,
#     page: Optional[int] = 1,
#     per_page: Optional[int] = 20,
#     search_term: Optional[str] = None,
#     repo: Repo = Depends(get_repo),
#     system_repo: Repo = Depends(get_system_repo),
# ):
#     search_term = request.query_params.get("q")
#     path_node_1_uri = await get_uri_for_curie_id(request.path_params["collectionId"])
#     path_node_2_uri = await get_uri_for_curie_id(request.path_params["catalogId"])
#     endpoint_uri = URIRef(request.scope.get("route").name)
#     return await listing_function(
#         request,
#         repo,
#         system_repo,
#         endpoint_uri,
#         hierarchy_level=3,
#         path_nodes={
#             "path_node_1": IRI(value=path_node_1_uri),
#             "path_node_2": IRI(value=path_node_2_uri),
#         },
#         page=page,
#         per_page=per_page,
#         search_term=search_term,
#     )

async def catalog_object(
        request: Request,
        repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(request.scope.get("route").name)
    object_uri = await get_uri_for_curie_id(request.path_params["catalogId"])
    return await object_function(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )


async def collection_object(
        request: Request,
        repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(request.scope.get("route").name)
    object_uri = await get_uri_for_curie_id(request.path_params["collectionId"])
    return await object_function(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )


async def item_object(
        request: Request,
        repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(request.scope.get("route").name)
    object_uri = await get_uri_for_curie_id(request.path_params["itemId"])
    return await object_function(
        request, endpoint_uri, object_uri, request_url, repo, system_repo
    )
