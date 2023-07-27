from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from rdflib import URIRef
from rdflib.term import _is_valid_uri

from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri

router = APIRouter(tags=["Identifier Resolution"])


@router.get(
    "/identifier/curie/{iri:path}",
    summary="Get the IRI's CURIE identifier",
    response_class=PlainTextResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"content": {"application/json": {}}},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"content": {"application/json": {}}},
    },
)
def get_curie_route(iri: str):
    if not _is_valid_uri(iri):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid characters in {iri}")
    try:
        return get_curie_id_for_uri(URIRef(iri))
    except ValueError as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Error processing IRI {iri}"
        ) from err
    except Exception as err:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Unhandled server error for IRI {iri}",
        ) from err


@router.get(
    "/identifier/iri/{curie}",
    summary="Get the CURIE identifier's fully qualified IRI",
    response_class=PlainTextResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"content": {"application/json": {}}},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"content": {"application/json": {}}},
    },
)
def get_iri_route(curie: str):
    try:
        return get_uri_for_curie_id(curie)
    except ValueError as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Invalid input '{curie}'. {err}"
        ) from err
    except Exception as err:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Unhandled server error for curie {curie}",
        ) from err
