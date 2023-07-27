import logging
from typing import Optional

from fastapi import APIRouter, Request
from rdflib import URIRef, SKOS, Literal, DCTERMS
from starlette.responses import PlainTextResponse

from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.vocprez_item import VocabItem
from prez.models.vocprez_listings import VocabMembers
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import (
    return_from_queries,
    return_profiles,
    return_from_graph,
)
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.methods import queries_to_graph
from prez.sparql.objects_listings import (
    generate_listing_construct,
    generate_listing_count_construct,
    generate_item_construct,
)
from prez.sparql.resource import get_resource
from prez.bnode import get_bnode_depth
from prez.services.vocprez import (
    get_concept_scheme_query,
    get_concept_scheme_top_concepts_query,
    get_concept_narrowers_query,
)
from prez.response import StreamingTurtleAnnotatedResponse
from prez.routers.curie import get_iri_route

router = APIRouter(tags=["VocPrez"])

log = logging.getLogger(__name__)


@router.get("/v", summary="VocPrez Home")
async def vocprez_home():
    return PlainTextResponse("VocPrez Home")


@router.get("/v/collection", summary="List Collections")
@router.get("/v/vocab", summary="List Vocabularies")
async def schemes_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of VocPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    vocprez_members = VocabMembers(url_path=str(request.url.path))
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=vocprez_members.classes
    )
    vocprez_members.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(vocprez_members.selected_class),
            prof_and_mt_info=prof_and_mt_info,
        )
    list_query, predicates_for_link_addition = generate_listing_construct(
        vocprez_members, prof_and_mt_info.profile, page, per_page
    )
    count_query = generate_listing_count_construct(vocprez_members)
    return await return_from_queries(
        [list_query, count_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        predicates_for_link_addition,
    )


@router.get(
    "/v/vocab/{concept_scheme_curie}",
    summary="Get a SKOS Concept Scheme",
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
    bnode_depth = get_bnode_depth(resource, iri)
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

    graph = await queries_to_graph([concept_scheme_top_concepts_query])
    for concept in graph.objects(iri, SKOS.hasTopConcept):
        if isinstance(concept, URIRef):
            concept_curie = get_curie_id_for_uri(concept)
            graph.add(
                (
                    concept,
                    PREZ.link,
                    Literal(f"/v/vocab/{concept_scheme_curie}/{concept_curie}"),
                )
            )
            graph.add(
                (
                    concept,
                    DCTERMS.identifier,
                    Literal(concept_curie, datatype=PREZ.identifier),
                )
            )

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

    graph = await queries_to_graph([concept_narrowers_query])
    for concept in graph.objects(iri, SKOS.narrower):
        if isinstance(concept, URIRef):
            concept_curie = get_curie_id_for_uri(concept)
            graph.add(
                (
                    concept,
                    PREZ.link,
                    Literal(f"/v/vocab/{concept_scheme_curie}/{concept_curie}"),
                )
            )
            graph.add(
                (
                    concept,
                    DCTERMS.identifier,
                    Literal(concept_curie, datatype=PREZ.identifier),
                )
            )

    return await return_from_graph(
        graph,
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
    )


@router.get(
    "/v/vocab/{concept_scheme_curie}/{concept_curie}",
    summary="Get a SKOS Concept",
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
    profiles_mediatypes_info = ProfilesMediatypesInfo(
        request=request, classes=frozenset([SKOS.Concept])
    )

    concept_iri = get_iri_route(concept_curie)
    graph = await get_resource(concept_iri)
    graph.add(
        (
            concept_iri,
            PREZ.link,
            Literal(f"/v/vocab/{concept_scheme_curie}/{concept_curie}"),
        )
    )
    graph.add(
        (
            concept_iri,
            DCTERMS.identifier,
            Literal(concept_curie, datatype=PREZ.identifier),
        )
    )

    return await return_from_graph(
        graph,
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
    )


@router.get("/v/collection/{collection_curie}", summary="Get Collection")
async def vocprez_collection(request: Request, collection_curie: str):
    return await item_endpoint(request)


@router.get("/v/collection/{collection_curie}/{concept_curie}", summary="Get Concept")
async def vocprez_collection_concept(
    request: Request, collection_curie: str, concept_curie: str
):
    return await item_endpoint(request)


@router.get("/v/object", summary="Get VocPrez Object")
async def item_endpoint(request: Request, vp_item: Optional[VocabItem] = None):
    """Returns a VocPrez skos:Concept, Collection, Vocabulary, or ConceptScheme in the requested profile & mediatype"""

    if not vp_item:
        vp_item = VocabItem(
            **request.path_params,
            **request.query_params,
            url_path=str(request.url.path),
        )
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=vp_item.classes)
    vp_item.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(vp_item.selected_class),
            prof_and_mt_info=prof_and_mt_info,
        )
    item_query = generate_item_construct(vp_item, prof_and_mt_info.profile)
    (
        item_members_query,
        predicates_for_link_addition,
    ) = generate_listing_construct(vp_item, prof_and_mt_info.profile, 1, 5000)
    return await return_from_queries(
        [item_query, item_members_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        predicates_for_link_addition,
    )
