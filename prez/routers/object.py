from string import Template
from typing import FrozenSet, Optional

from fastapi import APIRouter, Request, HTTPException, status, Query
from fastapi import Depends
from rdflib import Graph, Literal, URIRef, PROF, DCTERMS
from starlette.responses import PlainTextResponse

from prez.cache import (
    endpoints_graph_cache,
    profiles_graph_cache,
    links_ids_graph_cache,
)
from prez.dependencies import get_repo
from prez.models.listing import ListingModel
from prez.models.object_item import ObjectItem
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.queries.object import object_inbound_query, object_outbound_query
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph, return_profiles
from prez.routers.identifier import get_iri_route
from prez.services.curie_functions import get_curie_id_for_uri, get_uri_for_curie_id
from prez.services.model_methods import get_classes
from prez.services.objects import object_function
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import (
    get_endpoint_template_queries,
    generate_relationship_query,
    generate_item_construct,
    generate_listing_construct,
    generate_listing_count_construct,
)

router = APIRouter(tags=["Object"])


@router.get(
    "/count", summary="Get object's statement count", response_class=PlainTextResponse
)
async def count_route(
    curie: str,
    inbound: str = Query(
        None,
        examples={
            "skos:inScheme": {
                "summary": "skos:inScheme",
                "value": "http://www.w3.org/2004/02/skos/core#inScheme",
            },
            "skos:topConceptOf": {
                "summary": "skos:topConceptOf",
                "value": "http://www.w3.org/2004/02/skos/core#topConceptOf",
            },
            "empty": {"summary": "Empty", "value": None},
        },
    ),
    outbound: str = Query(
        None,
        examples={
            "empty": {"summary": "Empty", "value": None},
            "skos:hasTopConcept": {
                "summary": "skos:hasTopConcept",
                "value": "http://www.w3.org/2004/02/skos/core#hasTopConcept",
            },
        },
    ),
    repo=Depends(get_repo),
):
    """Get an Object's statements count based on the inbound or outbound predicate"""
    iri = get_iri_route(curie)

    if inbound is None and outbound is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "At least 'inbound' or 'outbound' is supplied a valid IRI.",
        )

    if inbound and outbound:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only provide one value for either 'inbound' or 'outbound', not both.",
        )

    if inbound:
        query = object_inbound_query(iri, inbound)
        _, rows = await repo.send_queries([], [(None, query)])
        for row in rows[0][1]:
            return row["count"]["value"]

    query = object_outbound_query(iri, outbound)
    _, rows = await repo.send_queries([], [(None, query)])
    for row in rows[0][1]:
        return row["count"]["value"]


@router.get("/object", summary="Object", name="https://prez.dev/endpoint/object")
async def object_route(request: Request, repo=Depends(get_repo)):
    return await object_function(request, repo=repo)
