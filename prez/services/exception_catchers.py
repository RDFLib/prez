import httpx
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.requests import Request

from prez.exceptions.model_exceptions import (
    ClassNotFoundException,
    InvalidSPARQLQueryException,
    NoEndpointNodeshapeException,
    NoProfilesException,
    PrefixNotBoundException,
    URINotFoundException, MissingFilterQueryError
)


async def catch_400(request: Request, exc: Exception):
    return JSONResponse(status_code=400, content=exc.__dict__)


async def catch_404(request: Request, exc: ValidationError):
    return JSONResponse(status_code=404, content=exc.__dict__)


async def catch_500(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


async def catch_class_not_found_exception(
    request: Request, exc: ClassNotFoundException
):
    return JSONResponse(
        status_code=404,
        content={
            "error": "NO_CLASS",
            "message": exc.message,
        },
    )


async def catch_uri_not_found_exception(request: Request, exc: URINotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "NO_URI",
            "message": exc.message,
        },
    )


async def catch_prefix_not_found_exception(
    request: Request, exc: PrefixNotBoundException
):
    return JSONResponse(
        status_code=404,
        content={
            "error": "NO_PREFIX",
            "message": exc.message,
        },
    )


async def catch_no_profiles_exception(request: Request, exc: NoProfilesException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "NO_PROFILES",
            "message": exc.message,
        },
    )


async def catch_invalid_sparql_query(
    request: Request, exc: InvalidSPARQLQueryException
):
    return JSONResponse(
        status_code=400,
        content={
            "error": "Bad Request",
            "detail": exc.message,
        },
    )


async def catch_no_endpoint_nodeshape_exception(
    request: Request, exc: NoEndpointNodeshapeException
):
    return JSONResponse(
        status_code=400,
        content={
            "error": "Bad Request",
            "detail": exc.message,
        },
    )

async def catch_missing_filter_query_param(
    request: Request, exc: MissingFilterQueryError
):
    return JSONResponse(
        status_code=400,
        content={
            "error": "Bad Request",
            "detail": exc.message,
        },
    )


async def catch_httpx_error(request: Request, exc: httpx.HTTPError):
    # Determine appropriate status code based on exception type
    if isinstance(exc, httpx.ConnectError):
        status_code = 503  # Service Unavailable
        error_type = "SPARQL_CONNECTION_ERROR"
    elif isinstance(exc, httpx.TimeoutException):
        status_code = 504  # Gateway Timeout
        error_type = "SPARQL_TIMEOUT_ERROR"
    else:
        status_code = 502  # Bad Gateway
        error_type = "SPARQL_ERROR"
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_type,
            "detail": str(exc),
        },
    )
