import json
from pathlib import Path

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
    generate_concept_hierarchy_query, cql_post_parser_dependency,
)
from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import EP, ONT, OGCE
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

router = APIRouter(tags=["ogcprez"])

responses_json = Path(__file__).parent / "rdf_response_examples.json"
responses = json.loads(responses_json.read_text())
# responses = {
#     200: {
#         "content": {
#             "application/ld+json": {
#                 "example": {
#                     "@id": "https://example.com/item/1",
#                     "https://example.com/property": "value"
#                 }
#             },
#             "application/anot+ld+json": {
#                 "example": {
#                     "@context": {"prez": "https://prez.dev/"},
#                     "@id": "https://example.com/item/1",
#                     "https://example.com/property": "value",
#                     "prez:label": "Item One"
#                 }
#             },
#             "application/rdf+xml": {
#                 "example": "<?xml version=\"1.0\"?>\n<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">\n    <rdf:Description rdf:about=\"https://example.com/item/1\">\n        <ns1:property xmlns:ns1=\"https://example.com/\">value</ns1:property>\n    </rdf:Description>\n</rdf:RDF>"
#             },
#             "text/anot+turtle": {
#                 "example": """
#                     @prefix prez: <https://prez.dev/> .
#
#                     <https://example.com/item/1>
#                         <https://example.com/property> "value" ;
#                         prez:label "Item One" .
#                 """
#             },
#             "text/turtle": {
#                 "example": """
#                     <https://example.com/item/1> <https://example.com/property> "value" .
#                 """
#             },
#         }
#     }
# }


# Path to the directory containing JSON files
cql_json_examples_dir = Path("__file__").parent / "examples/cql"

# Dictionary comprehension to create examples
cql_examples = {
    file.stem: {
        "summary": file.stem,
        "value": json.loads(file.read_text())
    }
    for file in cql_json_examples_dir.glob("*.json")
}


def create_path_param(name: str, description: str, example: str):
    return {
        "in": "path",
        "name": name,
        "required": True,
        "schema": {
            "type": "string",
            "example": example,
        },
        "description": description,
    }


path_parameters = {
    "collection-listing": [
        create_path_param("catalogId", "Curie of the Catalog ID.", "bblck-ctlg:bblocks")
    ],
    "item-listing": [
        create_path_param(
            "catalogId", "Curie of the Catalog ID.", "bblck-ctlg:bblocks"
        ),
        create_path_param(
            "collectionId", "Curie of the Collection ID.", "bblck-vcbs:api"
        ),
    ],
    "top-concepts": [
        create_path_param("parent_curie", "Parent CURIE.", "exm:SchemingConceptScheme")
    ],
    "narrowers": [
        create_path_param("parent_curie", "Parent CURIE.", "exm:TopLevelConcept")
    ],
    "profile-object": [
        create_path_param("profile_curie", "Profile CURIE.", "prez:OGCItemProfile")
    ],
    "catalog-object": [
        create_path_param("catalogId", "Catalog ID.", "bblck-ctlg:bblocks")
    ],
    "collection-object": [
        create_path_param("catalogId", "Catalog ID.", "bblck-ctlg:bblocks"),
        create_path_param("collectionId", "Collection ID.", "bblck-vcbs:api"),
    ],
    "item-object": [
        create_path_param("catalogId", "Catalog ID.", "bblck-ctlg:bblocks"),
        create_path_param("collectionId", "Collection ID.", "bblck-vcbs:api"),
        create_path_param("itemId", "Item ID.", "bblcks:ogc.unstable.sosa"),
    ],
}

openapi_extras = {
    name: {"parameters": params} for name, params in path_parameters.items()
}


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
    path="/search",
    summary="Search",
    name=OGCE["search"],
    responses=responses
)
@router.get(
    "/profiles",
    summary="List Profiles",
    name=EP["system/profile-listing"],
    responses=responses
)
@router.get(
    path="/cql",
    summary="CQL GET endpoint",
    name=OGCE["cql-get"],
    responses=responses
)
@router.get(
    "/catalogs",
    summary="Catalog Listing",
    name=OGCE["catalog-listing"],
    responses=responses
)
@router.get(
    "/catalogs/{catalogId}/collections",
    summary="Collection Listing",
    name=OGCE["collection-listing"],
    openapi_extra=openapi_extras.get("collection-listing"),
    responses=responses
)
@router.get(
    "/catalogs/{catalogId}/collections/{collectionId}/items",
    summary="Item Listing",
    name=OGCE["item-listing"],
    openapi_extra=openapi_extras.get("item-listing"),
    responses=responses
)
@router.get(
    "/concept-hierarchy/{parent_curie}/top-concepts",
    summary="Top Concepts",
    name=OGCE["top-concepts"],
    openapi_extra=openapi_extras.get("top-concepts"),
    responses=responses
)
@router.get(
    "/concept-hierarchy/{parent_curie}/narrowers",
    summary="Narrowers",
    name=OGCE["narrowers"],
    openapi_extra=openapi_extras.get("narrowers"),
    responses=responses
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


@router.post(
    path="/cql",
    summary="CQL POST endpoint",
    name=OGCE["cql-post"],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": cql_examples
                }
            }
        }
    },
    responses=responses
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
    )


########################################################################################################################
# Object endpoints

# 1: /object?uri=<uri>
# 2: /profiles/{profile_curie}
# 3: /catalogs/{catalogId}
# 4: /catalogs/{catalogId}/collections/{collectionId}
# 5: /catalogs/{catalogId}/collections/{collectionId}/items/{itemId}
########################################################################################################################


@router.get(
    path="/object",
    summary="Object",
    name=EP["system/object"],
    responses=responses
)
@router.get(
    path="/profiles/{profile_curie}",
    summary="Profile",
    name=EP["system/profile-object"],
    openapi_extra=openapi_extras.get("profile-object"),
    responses=responses
)
@router.get(
    path="/catalogs/{catalogId}",
    summary="Catalog Object",
    name=OGCE["catalog-object"],
    openapi_extra=openapi_extras.get("catalog-object"),
    responses=responses
)
@router.get(
    path="/catalogs/{catalogId}/collections/{collectionId}",
    summary="Collection Object",
    name=OGCE["collection-object"],
    openapi_extra=openapi_extras.get("collection-object"),
    responses=responses
)
@router.get(
    path="/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}",
    summary="Item Object",
    name=OGCE["item-object"],
    openapi_extra=openapi_extras.get("item-object"),
    responses=responses
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
