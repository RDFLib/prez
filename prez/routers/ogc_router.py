from typing import Optional

from fastapi import APIRouter, Depends

from prez.dependencies import (
    get_data_repo,
    get_system_repo,
    generate_search_query,
    cql_get_parser_dependency,
    get_endpoint_nodeshapes,
    get_negotiated_pmts,
    get_profile_nodeshape,
    get_endpoint_structure, generate_concept_hierarchy_query,
)
from prez.reference_data.prez_ns import EP, ONT, OGCE
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape
from temp.grammar import ConstructQuery

router = APIRouter(tags=["ogcprez"])


########################################################################################################################
# Listing endpoints

# 1: /profiles
# 2: /catalogs
# 3: /catalogs/{catalogId}/collections
# 4: /catalogs/{catalogId}/collections/{collectionId}/items
# 5: /concept-hierarchy/{parent_uri}/top-concepts
# 6: /concept-hierarchy/{parent_uri}/narrowers
########################################################################################################################


@router.get(
    "/profiles",
    summary="List Profiles",
    name=EP["system/profile-listing"],
)
@router.get(
    path="/cql",
    summary="CQL GET endpoint",
    name=OGCE["cql-get"],
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
@router.get(
    "/concept-hierarchy/{parent_curie}/top-concepts",
    summary="Top Concepts",
    name=OGCE["top-concepts"],
)
@router.get(
    "/concept-hierarchy/{parent_curie}/narrowers",
    summary="Narrowers",
    name=OGCE["narrowers"],
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
        concept_hierarchy_query: ConceptHierarchyQuery = Depends(generate_concept_hierarchy_query),
        data_repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    return await listing_function(
        data_repo=data_repo,
        system_repo=system_repo,
        endpoint_nodeshape=endpoint_nodeshape,
        endpoint_structure=endpoint_structure,
        search_query=search_query,
        concept_hierarchy_query=concept_hierarchy_query,
        cql_parser=cql_parser,
        pmts=pmts,
        profile_nodeshape=profile_nodeshape,
        page=page,
        per_page=per_page,
        order_by=order_by,
        order_by_direction=order_by_direction,
        original_endpoint_type=ONT["ListingEndpoint"],
    )


########################################################################################################################
# Object endpoints

# 1: /object?uri=<uri>
# 2: /profiles/{profile_curie}
# 3: /catalogs/{catalogId}
# 4: /catalogs/{catalogId}/collections/{collectionId}
# 5: /catalogs/{catalogId}/collections/{collectionId}/items/{itemId}
########################################################################################################################


@router.get(path="/object", summary="Object", name=EP["system/object"])
@router.get(
    path="/profiles/{profile_curie}",
    summary="Profile",
    name=EP["system/profile-object"],
)
@router.get(
    path="/catalogs/{catalogId}",
    summary="Catalog Object",
    name=OGCE["catalog-object"],
)
@router.get(
    path="/catalogs/{catalogId}/collections/{collectionId}",
    summary="Collection Object",
    name=OGCE["collection-object"],
)
@router.get(
    path="/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}",
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
    return await object_function(
        data_repo=data_repo,
        system_repo=system_repo,
        endpoint_structure=endpoint_structure,
        pmts=pmts,
        profile_nodeshape=profile_nodeshape,
    )
