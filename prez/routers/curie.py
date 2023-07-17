from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from rdflib import URIRef

from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri

router = APIRouter(tags=["Identifier Resolution"])


@router.get(
    "/identifier/curie/{iri:path}",
    summary="Get the IRI's CURIE identifier",
    response_class=PlainTextResponse,
)
def get_curie_route(iri: str):
    return get_curie_id_for_uri(URIRef(iri))


@router.get(
    "/identifier/iri/{curie}",
    summary="Get the CURIE identifier's fully qualified IRI",
    response_class=PlainTextResponse,
)
def get_iri_route(curie: str):
    return get_uri_for_curie_id(curie)
