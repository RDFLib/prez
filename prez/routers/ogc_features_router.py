from typing import Optional, List

from fastapi import Depends, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import StreamingResponse, JSONResponse

from prez.dependencies import (
    get_data_repo,
    cql_get_parser_dependency,
    get_url,
    get_ogc_features_mediatype,
    get_system_repo,
    get_endpoint_nodeshapes,
    get_profile_nodeshape,
    get_ogc_features_path_params,
    get_template_query,
    check_unknown_params,
    get_endpoint_uri_type,
)
from prez.exceptions.model_exceptions import (
    ClassNotFoundException,
    URINotFoundException,
    InvalidSPARQLQueryException,
    PrefixNotFoundException,
    NoProfilesException, NoEndpointNodeshapeException,
)
from prez.models.ogc_features import generate_landing_page_links, OGCFeaturesLandingPage
from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import OGCFEAT
from prez.repositories import Repo
from prez.routers.api_extras_examples import ogc_features_openapi_extras
from prez.routers.conformance import router as conformance_router
from prez.services.exception_catchers import (
    catch_400,
    catch_404,
    catch_500,
    catch_class_not_found_exception,
    catch_uri_not_found_exception,
    catch_invalid_sparql_query,
    catch_prefix_not_found_exception,
    catch_no_profiles_exception, catch_no_endpoint_nodeshape_exception,
)
from prez.services.listings import ogc_features_listing_function, generate_link_headers
from prez.services.objects import ogc_features_object_function
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape

ALLOWED_METHODS: List[str] = ["GET", "HEAD", "OPTIONS"]

features_subapi = FastAPI(
    title="OGC Features API",
    exception_handlers={
        400: catch_400,
        404: catch_404,
        500: catch_500,
        NoProfilesException: catch_no_profiles_exception,
        ClassNotFoundException: catch_class_not_found_exception,
        URINotFoundException: catch_uri_not_found_exception,
        PrefixNotFoundException: catch_prefix_not_found_exception,
        InvalidSPARQLQueryException: catch_invalid_sparql_query,
        NoEndpointNodeshapeException: catch_no_endpoint_nodeshape_exception,
    },
)
features_subapi.include_router(conformance_router)


@features_subapi.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder(
            {
                "detail": exc.errors(),
                "body": exc.body,
                "note": {
                    "This error was caught as a RequestValidationError which OGC Features "
                    "specification specifies should be raised with a status code of 400. "
                    "It would otherwise be a 422 Unprocessable Entity."
                },
            }
        ),
    )


@features_subapi.api_route(
    "/",
    summary="OGC Features API",
    methods=ALLOWED_METHODS,
)
async def ogc_features_api(
    url: str = Depends(get_url),
):
    links = generate_landing_page_links(url)
    link_headers = generate_link_headers(links)
    lp = OGCFeaturesLandingPage(
        title="OGC API - Features",
        description="This is a landing page for the OGC API - Features.",
        links=links,
    )
    return JSONResponse(
        content=lp.model_dump(),
        headers={"Content-Type": "application/json"} | link_headers,
    )


########################################################################################################################
# Listing endpoints

# 1: /features/collections
# 2: /features/collections/{collectionId}/items
########################################################################################################################


@features_subapi.api_route(
    "/queryables",
    methods=ALLOWED_METHODS,
    name=OGCFEAT["queryables-global"],
)
@features_subapi.api_route(
    "/collections/{collectionId}/queryables",
    methods=ALLOWED_METHODS,
    name=OGCFEAT["queryables-local"],
    openapi_extra=ogc_features_openapi_extras.get("feature-collection"),
)
@features_subapi.api_route(
    "/collections",
    methods=ALLOWED_METHODS,
    name=OGCFEAT["feature-collections"],
)
@features_subapi.api_route(
    "/collections/{collectionId}/items",
    methods=ALLOWED_METHODS,
    name=OGCFEAT["features"],
    openapi_extra=ogc_features_openapi_extras.get("feature-collection"),
)
async def listings_with_feature_collection(
    validate_unknown_params: bool = Depends(check_unknown_params),
    endpoint_uri_type: str = Depends(get_endpoint_uri_type),
    endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
    profile_nodeshape: NodeShape = Depends(get_profile_nodeshape),
    url: str = Depends(get_url),
    mediatype: str = Depends(get_ogc_features_mediatype),
    path_params: dict = Depends(get_ogc_features_path_params),
    query_params: QueryParams = Depends(),
    cql_parser: CQLParser = Depends(cql_get_parser_dependency),
    data_repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    try:
        content, headers = await ogc_features_listing_function(
            endpoint_uri_type,
            endpoint_nodeshape,
            profile_nodeshape,
            mediatype,
            url,
            data_repo,
            system_repo,
            cql_parser,
            query_params,
            **path_params,
        )
    except Exception as e:
        raise e
    return StreamingResponse(content=content, media_type=mediatype, headers=headers)


########################################################################################################################
# Object endpoints

# 1: /features/collections/{collectionId}
# 2: /features/collections/{collectionId}/items/{featureId}
########################################################################################################################


@features_subapi.api_route(
    path="/collections/{collectionId}",
    methods=ALLOWED_METHODS,
    name=OGCFEAT["feature-collection"],
    openapi_extra=ogc_features_openapi_extras.get("feature-collection"),
)
@features_subapi.api_route(
    path="/collections/{collectionId}/items/{featureId}",
    methods=ALLOWED_METHODS,
    name=OGCFEAT["feature"],
    openapi_extra=ogc_features_openapi_extras.get("feature"),
)
async def objects(
    template_query: Optional[str] = Depends(get_template_query),
    mediatype: str = Depends(get_ogc_features_mediatype),
    url: str = Depends(get_url),
    path_params: dict = Depends(get_ogc_features_path_params),
    data_repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    try:
        content, headers = await ogc_features_object_function(
            template_query,
            mediatype,
            url,
            data_repo,
            system_repo,
            **path_params,
        )
    except Exception as e:
        raise e
    return StreamingResponse(content=content, media_type=mediatype, headers=headers)
