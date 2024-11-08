import logging
from typing import List

from fastapi import APIRouter, Depends, Path
from rdflib import RDF, RDFS
from sparql_grammar_pydantic import ConstructQuery

from prez.cache import endpoints_graph_cache
from prez.dependencies import (
    cql_get_parser_dependency,
    generate_concept_hierarchy_query,
    generate_search_query,
    get_data_repo,
    get_endpoint_nodeshapes,
    get_endpoint_structure,
    get_negotiated_pmts,
    get_profile_nodeshape,
    get_system_repo,
)
from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import ONT
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.listings import listing_function
from prez.services.objects import object_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

logger = logging.getLogger(__name__)


def create_path_param(name: str, description: str, example: str):
    return Path(..., description=description, example=example)


# Dynamic route handler
def create_dynamic_route_handler(route_type: str):
    if route_type == "ListingEndpoint":

        async def dynamic_list_handler(
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

        return dynamic_list_handler
    elif route_type == "ObjectEndpoint":

        async def dynamic_object_handler(
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

        return dynamic_object_handler


# Extract path parameters from the path
def extract_path_params(path: str) -> List[str]:
    return [
        part[1:-1]
        for part in path.split("/")
        if part.startswith("{") and part.endswith("}")
    ]


# Add routes dynamically to the router
def add_routes(router: APIRouter):
    routes = []
    for s in endpoints_graph_cache.subjects(
        predicate=RDF.type, object=ONT.DynamicEndpoint
    ):
        if ONT.ListingEndpoint in endpoints_graph_cache.objects(
            subject=s, predicate=RDF.type
        ):
            route = {
                "path": str(endpoints_graph_cache.value(s, ONT.apiPath)),
                "name": str(s),
                "description": str(endpoints_graph_cache.value(s, RDFS.label)),
                "type": "ListingEndpoint",
            }
            routes.append(route)
        elif ONT.ObjectEndpoint in endpoints_graph_cache.objects(
            subject=s, predicate=RDF.type
        ):
            route = {
                "path": str(endpoints_graph_cache.value(s, ONT.apiPath)),
                "name": str(s),
                "description": str(endpoints_graph_cache.value(s, RDFS.label)),
                "type": "ObjectEndpoint",
            }
            routes.append(route)

    for route in routes:
        path_param_names = extract_path_params(route["path"])

        # Create path parameters using FastAPI's Path
        path_params = {
            param: create_path_param(
                param, f"Path parameter: {param}", f"example_{param}"
            )
            for param in path_param_names
        }

        # Create OpenAPI extras for path parameters
        openapi_extras = {
            "parameters": [
                {
                    "in": "path",
                    "name": name,
                    "required": True,
                    "schema": {"type": "string", "example": param.example},
                    "description": param.description,
                }
                for name, param in path_params.items()
            ]
        }

        # Create the endpoint function
        endpoint = create_dynamic_route_handler(route["type"])

        # Add the route to the router with OpenAPI extras
        router.add_api_route(
            name=route["name"],
            path=route["path"],
            endpoint=endpoint,
            methods=["GET"],
            description=route["description"],
            openapi_extra=openapi_extras,
        )

        logger.info(f"Added dynamic route: {route['path']}")


def create_dynamic_router() -> APIRouter:
    router = APIRouter(tags=["Custom Endpoints"])
    add_routes(router)
    return router
