import logging

from fastapi import APIRouter, Request
from rdflib import URIRef, SKOS
from starlette.responses import PlainTextResponse

from prez.bnode import get_bnode_depth
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.queries.vocprez import (
    get_concept_scheme_query,
    get_concept_scheme_top_concepts_query,
    get_concept_narrowers_query,
)
from prez.renderers.renderer import (
    return_from_queries,
    return_from_graph,
)
from prez.response import StreamingTurtleAnnotatedResponse
from prez.routers.identifier import get_iri_route
from prez.routers.object import item_function, listing_function, _add_prez_links
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.methods import rdf_query_to_graph
from prez.sparql.resource import get_resource

router = APIRouter(tags=["VocPrez"])

log = logging.getLogger(__name__)


@router.get("/v", summary="VocPrez Home")
async def vocprez_home():
    return PlainTextResponse("VocPrez Home")


@router.get(
    "/v/collection",
    summary="List Collections",
    name="https://prez.dev/endpoint/vocprez/collection-listing",
)
@router.get(
    "/v/vocab",
    summary="List Vocabularies",
    name="https://prez.dev/endpoint/vocprez/vocabs-listing",
)
async def collection_vocab_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    return await listing_function(request, page, per_page)


@router.get(
    "/v/vocab/{scheme_curie}/all",
    summary="Get Concept Scheme and all its concepts",
    name="https://prez.dev/endpoint/vocprez/vocab",
)
async def vocprez_scheme(request: Request, scheme_curie: str):
    """Get a SKOS Concept Scheme and all of its concepts.

    Note: This may be a very expensive operation depending on the size of the concept scheme.
    """
    return await item_function(request, object_curie=scheme_curie)


@router.get(
    "/v/vocab/{concept_scheme_curie}",
    summary="Get a SKOS Concept Scheme",
    name="https://prez.dev/endpoint/vocprez/collection",
    response_class=StreamingTurtleAnnotatedResponse,
    responses={
        200: {
            "content": {"text/turtle": {}},
        },
    },
)
async def concept_scheme_route(request: Request, concept_scheme_curie: str):
    """Get a SKOS Concept Scheme.

    `prez:childrenCount` is an `xsd:integer` count of the number of top concepts for this Concept Scheme.
    """
    profiles_mediatypes_info = ProfilesMediatypesInfo(
        request=request, classes=frozenset([SKOS.ConceptScheme])
    )

    iri = get_iri_route(concept_scheme_curie)
    resource = await get_resource(iri)
    bnode_depth = get_bnode_depth(iri, resource)
    concept_scheme_query = get_concept_scheme_query(iri, bnode_depth)

    return await return_from_queries(
        [concept_scheme_query],
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
    )


@router.get(
    "/v/vocab/{concept_scheme_curie}/top-concepts",
    summary="Get a SKOS Concept Scheme's top concepts",
    response_class=StreamingTurtleAnnotatedResponse,
    responses={
        200: {
            "content": {"text/turtle": {}},
        },
    },
)
async def concept_scheme_top_concepts_route(
    request: Request,
    concept_scheme_curie: str,
    page: int = 1,
    per_page: int = 20,
):
    """Get a SKOS Concept Scheme's top concepts.

    `prez:childrenCount` is an `xsd:integer` count of the number of top concepts for this Concept Scheme.
    """
    profiles_mediatypes_info = ProfilesMediatypesInfo(
        request=request, classes=frozenset([SKOS.ConceptScheme])
    )

    iri = get_iri_route(concept_scheme_curie)
    concept_scheme_top_concepts_query = get_concept_scheme_top_concepts_query(
        iri, page, per_page
    )

    graph = await rdf_query_to_graph(concept_scheme_top_concepts_query)
    for concept in graph.objects(iri, SKOS.hasTopConcept):
        if isinstance(concept, URIRef):
            concept_curie = get_curie_id_for_uri(concept)
    if "anot+" in profiles_mediatypes_info.mediatype:
        await _add_prez_links(graph)
    return await return_from_graph(
        graph,
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
    )


@router.get(
    "/v/vocab/{concept_scheme_curie}/{concept_curie}/narrowers",
    summary="Get a SKOS Concept's narrower concepts",
    response_class=StreamingTurtleAnnotatedResponse,
    responses={
        200: {
            "content": {"text/turtle": {}},
        },
    },
)
async def concept_narrowers_route(
    request: Request,
    concept_scheme_curie: str,
    concept_curie: str,
    page: int = 1,
    per_page: int = 20,
):
    """Get a SKOS Concept's narrower concepts.

    `prez:childrenCount` is an `xsd:integer` count of the number of narrower concepts for this concept.
    """
    profiles_mediatypes_info = ProfilesMediatypesInfo(
        request=request, classes=frozenset([SKOS.Concept])
    )

    iri = get_iri_route(concept_curie)
    concept_narrowers_query = get_concept_narrowers_query(iri, page, per_page)

    graph = await rdf_query_to_graph(concept_narrowers_query)
    if "anot+" in profiles_mediatypes_info.mediatype:
        await _add_prez_links(graph)
    return await return_from_graph(
        graph,
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
    )


@router.get(
    "/v/vocab/{concept_scheme_curie}/{concept_curie}",
    summary="Get a SKOS Concept",
    name="https://prez.dev/endpoint/vocprez/vocab-concept",
    response_class=StreamingTurtleAnnotatedResponse,
    responses={
        200: {
            "content": {"text/turtle": {}},
        },
    },
)
async def concept_route(
    request: Request, concept_scheme_curie: str, concept_curie: str
):
    """Get a SKOS Concept."""
    return await item_function(request, object_curie=concept_curie)


@router.get(
    "/v/collection/{collection_curie}",
    summary="Get Collection",
    name="https://prez.dev/endpoint/vocprez/collection",
)
async def vocprez_collection(request: Request, collection_curie: str):
    return await item_function(request, object_curie=collection_curie)


@router.get(
    "/v/collection/{collection_curie}/{concept_curie}",
    summary="Get Concept",
    name="https://prez.dev/endpoint/vocprez/collection-concept",
)
async def vocprez_collection_concept(
    request: Request, collection_curie: str, concept_curie: str
):
    return await item_function(request, object_curie=concept_curie)
