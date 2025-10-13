from typing import Optional

from fastapi import APIRouter, Depends, Query
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
    get_system_repo,
    get_url,
)
from prez.models.query_params import ListingQueryParams, ObjectQueryParams
from prez.reference_data.prez_ns import EP, OGCE, ONT
from prez.repositories import Repo
from prez.routers.api_extras_examples import (
    cql_examples,
    ogc_extended_openapi_extras,
    responses,
)
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.listings import listing_function, listing_profiles
from prez.services.objects import object_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

router = APIRouter(tags=["ogcprez"])


@router.get(
    "/profiles",
    summary="List Profiles",
    name=EP["system/profile-listing"],
    responses=responses,
)
async def listing_for_profiles(
    query_params: ListingQueryParams = Depends(),
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    data_repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    return await listing_profiles(data_repo, system_repo, query_params, pmts)


@router.get(path="/search", summary="Search", name=OGCE["search"], responses=responses)
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
    query_params: ListingQueryParams = Depends(),
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
        url=url,
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
    query_params: ListingQueryParams = Depends(),
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
        url=url,
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
    query_params: ObjectQueryParams = Depends(),
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure),
    profile_nodeshape: NodeShape = Depends(
        get_profile_nodeshape
    ),  # iri for object endpoint is used here
    data_repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
    url: str = Depends(get_url),
    iri: str = Query(
        None,
        description="The IRI of the object to retrieve.",
        include_in_schema=True,
        example="https://example.com/demo-vocabs/image-test/apron-image",
    ),
    uri: str = Query(
        None,
        description="The URI of the object to retrieve. Use 'iri' instead. This will be "
        "deprecated in a future version. Functionally the same as the 'iri' query "
        "parameter.",
        include_in_schema=True,
        deprecated=True,
    ),
    mediatype: str = Query(
        default="text/anot+turtle",
        alias="_mediatype",
        description="Requested mediatype",
    ),
    profile: Optional[str] = Query(
        default=None, alias="_profile", description="Requested profile"
    ),
):
    return await object_function(
        query_params=query_params,
        data_repo=data_repo,
        system_repo=system_repo,
        endpoint_structure=endpoint_structure,
        pmts=pmts,
        profile_nodeshape=profile_nodeshape,
        url=url,
    )
