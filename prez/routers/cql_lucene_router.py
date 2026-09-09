from fastapi import APIRouter, Depends
from sparql_grammar import ConstructQuery

from prez.dependencies import (
    generate_concept_hierarchy_query,
    generate_lucene_cql_search_query,
    generate_lucene_cql_search_query_post,
    get_data_repo,
    get_endpoint_nodeshapes,
    get_endpoint_structure,
    get_endpoint_structure_listing_post,
    get_negotiated_pmts,
    get_negotiated_pmts_listing_post,
    get_profile_nodeshape,
    get_profile_nodeshape_listing_post,
    get_system_repo,
    get_url,
    listing_post_params_dependency,
    lucene_cql_get_parser_dependency,
    lucene_cql_post_parser_dependency,
)
from prez.models.query_params import ListingQueryParams
from prez.reference_data.prez_ns import OGCE, ONT
from prez.repositories import Repo
from prez.routers.api_extras_examples import cql_examples, responses
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.listings import listing_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

router = APIRouter(tags=["ogcprez"])


@router.get(
    "/cql",
    summary="Lucene-backed CQL GET endpoint",
    name=OGCE["cql-get"],
    responses=responses,
)
async def lucene_cql_get(
    query_params: ListingQueryParams = Depends(),
    endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure),
    profile_nodeshape: NodeShape = Depends(get_profile_nodeshape),
    cql_parser: CQLParser | None = Depends(lucene_cql_get_parser_dependency),
    search_query: ConstructQuery = Depends(generate_lucene_cql_search_query),
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
    "/cql",
    summary="Lucene-backed CQL POST endpoint",
    name=OGCE["cql-post"],
    responses=responses,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "filter": {"type": "object"},
                            "facets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "page": {"type": "integer", "default": 1},
                            "limit": {"type": "integer", "minimum": 1},
                            "offset": {"type": "integer", "minimum": 0},
                            "facet_profile": {"type": "string"},
                            "_mediatype": {"type": "string"},
                            "_profile": {"type": "string"},
                        },
                        "examples": cql_examples,
                    }
                }
            }
        }
    },
)
async def lucene_cql_post(
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),
    endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts_listing_post),
    endpoint_structure: tuple[str, ...] = Depends(get_endpoint_structure_listing_post),
    profile_nodeshape: NodeShape = Depends(get_profile_nodeshape_listing_post),
    cql_parser: CQLParser | None = Depends(lucene_cql_post_parser_dependency),
    search_query: ConstructQuery = Depends(generate_lucene_cql_search_query_post),
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
