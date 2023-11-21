import logging

from fastapi import APIRouter, Request
from fastapi import Depends
from fastapi.responses import RedirectResponse
from rdflib import URIRef, SKOS
from starlette.responses import PlainTextResponse

from prez.bnode import get_bnode_depth
from prez.dependencies import get_repo
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.queries.vocprez import (
    get_concept_scheme_query,
    get_concept_scheme_top_concepts_query,
    get_concept_narrowers_query,
)
from prez.renderers.renderer import (
    return_from_graph,
)
from prez.response import StreamingTurtleAnnotatedResponse
from prez.routers.identifier import get_iri_route
from prez.services.objects import object_function
from prez.services.listings import listing_function
from prez.services.link_generation import _add_prez_links
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.methods import Repo
from prez.sparql.resource import get_resource

router = APIRouter(tags=["VocPrez"])

log = logging.getLogger(__name__)


@router.get("/v", summary="VocPrez Home")
async def vocprez_home():
    return PlainTextResponse("VocPrez Home")


@router.get(
    "/v/vocab",
    summary="List Vocabularies",
    name="https://prez.dev/endpoint/vocprez/vocabs-listing",
)
async def vocab_endpoint(
    request: Request,
    repo: Repo = Depends(get_repo),
    page: int = 1,
    per_page: int = 20,
):
    return await listing_function(
        request=request, page=page, per_page=per_page, repo=repo
    )


@router.get(
    "/v/collection",
    summary="List Collections",
    name="https://prez.dev/endpoint/vocprez/collection-listing",
)
async def collection_endpoint(
    request: Request,
    repo: Repo = Depends(get_repo),
    page: int = 1,
    per_page: int = 20,
):
    return await listing_function(
        request=request, page=page, per_page=per_page, repo=repo
    )


@router.get(
    "/v/vocab/{scheme_curie}/all",
    summary="Get Concept Scheme and all its concepts",
    name="https://prez.dev/endpoint/vocprez/vocab",
)
async def vocprez_scheme(
    request: Request, scheme_curie: str, repo: Repo = Depends(get_repo)
):
    """Get a SKOS Concept Scheme and all of its concepts.

    Note: This may be a very expensive operation depending on the size of the concept scheme.
    """
    return await object_function(request, object_curie=scheme_curie, repo=repo)


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
async def concept_scheme_route(
    request: Request,
    concept_scheme_curie: str,
    repo: Repo = Depends(get_repo),
):
    """Get a SKOS Concept Scheme.

    `prez:childrenCount` is an `xsd:integer` count of the number of top concepts for this Concept Scheme.
    """
    profiles_mediatypes_info = ProfilesMediatypesInfo(
        request=request, classes=frozenset([SKOS.ConceptScheme])
    )

    if (
        str(profiles_mediatypes_info.mediatype) != "text/anot+turtle"
        or str(profiles_mediatypes_info.mediatype) == "text/anot+turtle"
        and str(profiles_mediatypes_info.profile) != "https://w3id.org/profile/vocpub"
    ):
        return RedirectResponse(
            f"{request.url.path}/all{'?' if request.url.query else ''}{request.url.query}"
        )

    iri = get_iri_route(concept_scheme_curie)
    resource = await get_resource(iri, repo)
    bnode_depth = get_bnode_depth(iri, resource)
    concept_scheme_query = get_concept_scheme_query(iri, bnode_depth)
    item_graph, _ = await repo.send_queries([concept_scheme_query], [])
    return await return_from_graph(
        item_graph,
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
        profiles_mediatypes_info.selected_class,
        repo,
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
    repo: Repo = Depends(get_repo),
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

    graph, _ = await repo.send_queries([concept_scheme_top_concepts_query], [])
    for concept in graph.objects(iri, SKOS.hasTopConcept):
        if isinstance(concept, URIRef):
            concept_curie = get_curie_id_for_uri(concept)
    if "anot+" in profiles_mediatypes_info.mediatype:
        await _add_prez_links(graph, repo)
    return await return_from_graph(
        graph,
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
        profiles_mediatypes_info.selected_class,
        repo,
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
    repo: Repo = Depends(get_repo),
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

    graph, _ = await repo.send_queries([concept_narrowers_query], [])
    if "anot+" in profiles_mediatypes_info.mediatype:
        await _add_prez_links(graph, repo)
    return await return_from_graph(
        graph,
        profiles_mediatypes_info.mediatype,
        profiles_mediatypes_info.profile,
        profiles_mediatypes_info.profile_headers,
        profiles_mediatypes_info.selected_class,
        repo,
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
    request: Request,
    concept_scheme_curie: str,
    concept_curie: str,
    repo: Repo = Depends(get_repo),
):
    """Get a SKOS Concept."""
    return await object_function(request, object_curie=concept_curie, repo=repo)


@router.get(
    "/v/collection/{collection_curie}",
    summary="Get Collection",
    name="https://prez.dev/endpoint/vocprez/collection",
)
async def vocprez_collection(
    request: Request,
    collection_curie: str,
    repo: Repo = Depends(get_repo),
):
    return await object_function(request, object_curie=collection_curie, repo=repo)


@router.get(
    "/v/collection/{collection_curie}/{concept_curie}",
    summary="Get Concept",
    name="https://prez.dev/endpoint/vocprez/collection-concept",
)
async def vocprez_collection_concept(
    request: Request,
    collection_curie: str,
    concept_curie: str,
    repo: Repo = Depends(get_repo),
):
    return await object_function(request, object_curie=concept_curie, repo=repo)
