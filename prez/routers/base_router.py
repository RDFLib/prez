from fastapi import APIRouter, Depends
from sparql_grammar_pydantic import ConstructQuery

from prez.dependencies import (
    cql_get_parser_dependency,
    cql_post_parser_dependency,
    generate_concept_hierarchy_query,
    generate_search_query,
    get_data_repo,
    get_endpoint_nodeshapes,
    get_endpoint_structure,
    get_negotiated_pmts,
    get_profile_nodeshape,
    get_system_repo, get_url,
)
from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import EP, OGCE, ONT
from prez.repositories import Repo
from prez.routers.api_extras_examples import (
    cql_examples,
    ogc_extended_openapi_extras,
    responses,
)
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

router = APIRouter(tags=["ogcprez"])


@router.get(path="/search", summary="Search", name=OGCE["search"], responses=responses)
@router.get(
    "/profiles",
    summary="List Profiles",
    name=EP["system/profile-listing"],
    responses=responses,
)
@router.get(
    path="/cql", summary="CQL GET endpoint", name=OGCE["cql-get"], responses=responses
)
@router.get(
    "/concept-hierarchy/{parent_curie}/top-concepts",
    summary="Top Concepts",
    name=OGCE["top-concepts"],
    openapi_extra=ogc_extended_openapi_extras.get("top-concepts"),
    responses=responses,
)
@router.get(
    "/concept-hierarchy/{parent_curie}/narrowers",
    summary="Narrowers",
    name=OGCE["narrowers"],
    openapi_extra=ogc_extended_openapi_extras.get("narrowers"),
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
    url: str = Depends(get_url),
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
        url=url
    )


@router.post(
    path="/cql",
    summary="CQL POST endpoint",
    name=OGCE["cql-post"],
    openapi_extra={
        "requestBody": {"content": {"application/json": {"examples": cql_examples}}}
    },
    responses=responses,
)
async def cql_post_listings(
    query_params: QueryParams = Depends(),
    endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure),
    profile_nodeshape: NodeShape = Depends(get_profile_nodeshape),
    cql_parser: CQLParser = Depends(cql_post_parser_dependency),
    search_query: ConstructQuery = Depends(generate_search_query),
    data_repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
    url: str = Depends(get_url),
):
    return await listing_function(
        data_repo=data_repo,
        system_repo=system_repo,
        endpoint_nodeshape=endpoint_nodeshape,
        endpoint_structure=endpoint_structure,
        search_query=search_query,
        concept_hierarchy_query=None,
        cql_parser=cql_parser,
        pmts=pmts,
        profile_nodeshape=profile_nodeshape,
        query_params=query_params,
        original_endpoint_type=ONT["ListingEndpoint"],
        url=url
    )


########################################################################################################################
# Object endpoints

# 1: /object?uri=<uri>
# 2: /profiles/{profile_curie}
########################################################################################################################


@router.get(
    path="/object", summary="Object", name=EP["system/object"], responses=responses
)
@router.get(
    path="/profiles/{profile_curie}",
    summary="Profile",
    name=EP["system/profile-object"],
    openapi_extra=ogc_extended_openapi_extras.get("profile-object"),
    responses=responses,
)
async def objects(
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure),
    profile_nodeshape: NodeShape = Depends(get_profile_nodeshape),
    data_repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
    url: str = Depends(get_url),
):
    return await object_function(
        data_repo=data_repo,
        system_repo=system_repo,
        endpoint_structure=endpoint_structure,
        pmts=pmts,
        profile_nodeshape=profile_nodeshape,
        url=url
    )
