from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.responses import PlainTextResponse, RedirectResponse
from rdflib import URIRef
from rdflib.term import _is_valid_uri

from prez.dependencies import get_repo
from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri
from prez.queries.identifier import get_foaf_homepage_query

router = APIRouter(tags=["Identifier Resolution"])


@router.get(
    "/identifier/redirect",
    summary="Get a redirect response to the resource landing page",
    response_class=RedirectResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"content": {"application/json": {}}},
    },
)
async def get_identifier_redirect_route(
    iri: str, request: Request, repo=Depends(get_repo)
):
    """
    The `iri` query parameter is used to return a redirect response with the value from the `foaf:homepage` lookup.
    If no value is found, a 404 HTTP response is returned.
    """
    query = get_foaf_homepage_query(iri)
    _, rows = await repo.send_queries([], [(None, query)])
    url = None
    for row in rows[0][1]:
        url = row["url"]["value"]

    if url is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No homepage found for IRI {iri}."
        )

    # Note: currently does not forward query parameters but we may want to implement this in the future.
    return RedirectResponse(url, headers=request.headers)


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
