from fastapi import APIRouter, Depends
from sparql_grammar_pydantic import ConstructQuery

from prez.dependencies import (
    get_data_repo,
    get_system_repo,
    generate_search_query,
    cql_get_parser_dependency,
    get_endpoint_nodeshapes,
    get_negotiated_pmts,
    get_profile_nodeshape,
    get_endpoint_structure,
    generate_concept_hierarchy_query,
)
from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import EP, ONT, OGCFEAT, OGCE
from prez.repositories import Repo
from prez.routers.api_extras_examples import responses, openapi_extras
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

router = APIRouter(tags=["ogcfeatures"])


@router.get(path="/search", summary="Search", name=OGCE["search"], responses=responses)
@router.get(
    "/profiles",
    summary="List Profiles",
    name=EP["system/profile-listing"],
    responses=responses,
)
@router.get(
    "/collections",
    summary="Feature Collection Listing",
    name=OGCFEAT["feature-collection-listing"],
    openapi_extra=openapi_extras.get("feature-collection-listing"),
    responses=responses,
)
@router.get(
    "/collections/{collectionId}/items",
    summary="Feature Listing",
    name=OGCFEAT["feature-listing"],
    openapi_extra=openapi_extras.get("feature-listing"),
    responses=responses,
)
@router.get(
    "/concept-hierarchy/{parent_curie}/top-concepts",
    summary="Top Concepts",
    name=OGCFEAT["top-concepts"],
    openapi_extra=openapi_extras.get("top-concepts"),
    responses=responses,
)
@router.get(
    "/concept-hierarchy/{parent_curie}/narrowers",
    summary="Narrowers",
    name=OGCFEAT["narrowers"],
    openapi_extra=openapi_extras.get("narrowers"),
    responses=responses,
)
async def listings(
    query_params: QueryParams = Depends(),
    endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure),
    profile_nodeshape: NodeShape = Depends(get_profile_nodeshape),
    cql_parser: CQLParser = Depends(cql_get_parser_dependency),
    search_query: ConstructQuery = Depends(generate_search_query),
    concept_hierarchy_query: ConceptHierarchyQuery = Depends(
        generate_concept_hierarchy_query
    ),
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
        query_params=query_params,
        original_endpoint_type=ONT["ListingEndpoint"],
    )


########################################################################################################################
# Object endpoints

# 1: /object?uri=<uri>
# 2: /profiles/{profile_curie}
# 4: /collections/{collectionId}
# 5: /collections/{collectionId}/items/{itemId}
########################################################################################################################


@router.get(
    path="/object", summary="Object", name=EP["system/object"], responses=responses
)
@router.get(
    path="/profiles/{profile_curie}",
    summary="Profile",
    name=EP["system/profile-object"],
    openapi_extra=openapi_extras.get("profile-object"),
    responses=responses,
)
@router.get(
    path="/collections/{collectionId}",
    summary="Feature Collection Object",
    name=OGCFEAT["feature-collection-object"],
    openapi_extra=openapi_extras.get("feature-collection-object"),
    responses=responses,
)
@router.get(
    path="/collections/{collectionId}/items/{itemId}",
    summary="Feature Object",
    name=OGCFEAT["feature-object"],
    openapi_extra=openapi_extras.get("feature-object"),
    responses=responses,
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
