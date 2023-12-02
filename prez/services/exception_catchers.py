from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.requests import Request

from prez.exceptions.model_exceptions import (
    ClassNotFoundException,
    URINotFoundException,
    NoProfilesException, InvalidSPARQLQueryException,
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


async def catch_no_profiles_exception(request: Request, exc: NoProfilesException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "NO_PROFILES",
            "message": exc.message,
        },
    )


async def catch_invalid_sparql_query(request: Request, exc: InvalidSPARQLQueryException):
    return JSONResponse(
        status_code=400,
        content={
            "error": "Bad Request",
            "detail": exc.message,
        },
    )