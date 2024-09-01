from typing import Optional

from fastapi import Depends, FastAPI
from rdflib import Namespace
from starlette.responses import StreamingResponse

from prez.dependencies import (
    get_data_repo,
    cql_get_parser_dependency, get_url_path, get_ogc_features_mediatype, get_system_repo
)
from prez.exceptions.model_exceptions import ClassNotFoundException, URINotFoundException, InvalidSPARQLQueryException, \
    PrefixNotFoundException
from prez.models.ogc_features import generate_landing_page_links, Link, OGCFeaturesLandingPage
from prez.models.query_params import OGCFeaturesQueryParams
from prez.reference_data.prez_ns import EP, OGCFEAT
from prez.repositories import Repo
from prez.routers.api_extras_examples import responses
from prez.routers.conformance import router as conformance_router
from prez.services.exception_catchers import catch_400, catch_404, catch_500, catch_class_not_found_exception, \
    catch_uri_not_found_exception, catch_invalid_sparql_query, catch_prefix_not_found_exception
from prez.services.listings import ogc_features_listing_function
from prez.services.objects import ogc_features_object_function
from prez.services.query_generation.cql import CQLParser


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


@features_subapi.get(
    "/", summary="OGC Features API"
)
async def ogc_features_api(
    url_path: str = Depends(get_url_path),
):
    links = generate_landing_page_links(url_path)
    return OGCFeaturesLandingPage(
        title="OGC API - Features",
        description="This is a landing page for the OGC API - Features.",
        links=[Link(**link) for link in links]
    )


########################################################################################################################
# Listing endpoints

# 1: /features/collections
# 2: /features/collections/{collectionId}/items
########################################################################################################################

@features_subapi.get(
    "/collections",
    # summary="Collection Listing",
    name=OGCFEAT["feature-collections"],
    # openapi_extra=openapi_extras.get("collection-listing"),
    # responses=responses,
)
@features_subapi.get(
    "/collections/{collectionId}/items",
    # summary="Item Listing",
    name=OGCFEAT["features"],
    # openapi_extra=openapi_extras.get("item-listing"),
    # responses=responses,
)
async def listings(
        url_path: str = Depends(get_url_path),
        mediatype: str = Depends(get_ogc_features_mediatype),
        collectionId: Optional[str] = None,
        query_params: OGCFeaturesQueryParams = Depends(),
        cql_parser: CQLParser = Depends(cql_get_parser_dependency),
        data_repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    try:
        content, headers = await ogc_features_listing_function(
            mediatype,
            url_path,
            collectionId,
            data_repo,
            system_repo,
            cql_parser,
            query_params,
        )
    except Exception:
        raise
    return StreamingResponse(
        content=content, media_type=mediatype, headers=headers
    )


########################################################################################################################
# Object endpoints

# 1: /object?uri=<uri>
# 2: /features/collections/{collectionId}
# 3: /features/collections/{collectionId}/items/{featureId}
########################################################################################################################


@features_subapi.get(
    path="/object", summary="Object", name=EP["system/object"], responses=responses
)
@features_subapi.get(
    path="/collections/{collectionId}",
    # summary="Collection Object",
    name=OGCFEAT["feature-collection"],
    # openapi_extra=openapi_extras.get("collection-object"),
    # responses=responses,
)
@features_subapi.get(
    path="/collections/{collectionId}/items/{featureId}",
    # summary="Item Object",
    name=OGCFEAT["feature"],
    # openapi_extra=openapi_extras.get("item-object"),
    # responses=responses,
)
async def objects(
        mediatype: str = Depends(get_ogc_features_mediatype),
        url_path: str = Depends(get_url_path),
        collectionId: str = None,
        featureId: Optional[str] = None,
        data_repo: Repo = Depends(get_data_repo),
        system_repo: Repo = Depends(get_system_repo),
):
    props = None  # can define which props here to filter props
    try:
        content, headers = await ogc_features_object_function(
            mediatype,
            url_path,
            collectionId,
            featureId,
            data_repo,
            system_repo,
        )
    except Exception:
        raise
    return StreamingResponse(
        content=content, media_type=mediatype, headers=headers
    )
