from typing import Optional, List

from fastapi import Depends, FastAPI
from sparql_grammar_pydantic import ConstructQuery
from starlette.responses import StreamingResponse

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
from prez.exceptions.model_exceptions import ClassNotFoundException, URINotFoundException, InvalidSPARQLQueryException, \
    PrefixNotFoundException
from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import EP, ONT, OGCE
from prez.repositories import Repo
from prez.routers.api_extras_examples import responses, openapi_extras
from prez.routers.conformance import router as conformance_router
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.exception_catchers import catch_400, catch_404, catch_500, catch_class_not_found_exception, \
    catch_uri_not_found_exception, catch_invalid_sparql_query, catch_prefix_not_found_exception
from prez.services.listings import listing_function
from prez.services.objects import ogc_features_object_function
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

features_subapi = FastAPI(
    title="OGC Features API",
    exception_handlers={
        400: catch_400,
        404: catch_404,
        500: catch_500,
        ClassNotFoundException: catch_class_not_found_exception,
        URINotFoundException: catch_uri_not_found_exception,
        PrefixNotFoundException: catch_prefix_not_found_exception,
        InvalidSPARQLQueryException: catch_invalid_sparql_query,
    }
)
features_subapi.include_router(conformance_router)


########################################################################################################################
# Listing endpoints

# 1: /features/collections
# 2: /features/collections/{collectionId}/items
########################################################################################################################

@features_subapi.get(
    "/collections",
    summary="Collection Listing",
    name=OGCE["collection-listing"],
    openapi_extra=openapi_extras.get("collection-listing"),
    responses=responses,
)
@features_subapi.get(
    "/collections/{collectionId}/items",
    summary="Item Listing",
    name=OGCE["item-listing"],
    openapi_extra=openapi_extras.get("item-listing"),
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
# 2: /features/collections/{collectionId}
# 3: /features/collections/{collectionId}/items/{itemId}
########################################################################################################################


@features_subapi.get(
    path="/object", summary="Object", name=EP["system/object"], responses=responses
)
@features_subapi.get(
    path="/collections/{collectionId}",
    # summary="Collection Object",
    # name=OGCE["collection-object"],
    # openapi_extra=openapi_extras.get("collection-object"),
    # responses=responses,
)
@features_subapi.get(
    path="/collections/{collectionId}/items/{itemId}",
    # summary="Item Object",
    # name=OGCE["item-object"],
    # openapi_extra=openapi_extras.get("item-object"),
    # responses=responses,
)
async def objects(
        collectionId: str = None,
        itemId: Optional[str] = None,
        data_repo: Repo = Depends(get_data_repo),
):
    props = None  # can define which props here to filter props
    try:
        content, headers = await ogc_features_object_function(
            collectionId,
            itemId,
            props,
            data_repo,
        )
    except Exception:
        raise
    return StreamingResponse(
        content=content, media_type="turtle", headers=headers
    )
