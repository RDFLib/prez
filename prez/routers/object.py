from string import Template

from fastapi import APIRouter, Request
from rdflib import Graph, Literal, URIRef
from fastapi import APIRouter, Request, HTTPException, status, Query
from starlette.responses import PlainTextResponse

from prez.cache import endpoints_graph_cache
from prez.models.object_item import ObjectItem
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.methods import send_queries
from prez.sparql.objects_listings import (
    get_endpoint_template_queries,
    generate_relationship_query,
    generate_item_construct,
)
from prez.models import SpatialItem, VocabItem, CatalogItem
from prez.routers.identifier import get_iri_route
from prez.sparql.methods import sparql_query_non_async
from prez.queries.object import object_inbound_query, object_outbound_query

router = APIRouter(tags=["Object"])


@router.get(
    "/count", summary="Get object's statement count", response_class=PlainTextResponse
)
def count_route(
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

    if inbound is not None:
        query = object_inbound_query(iri, inbound)
        _, rows = sparql_query_non_async(query)
        for row in rows:
            return row["count"]["value"]

    query = object_outbound_query(iri, outbound)
    _, rows = sparql_query_non_async(query)
    for row in rows:
        return row["count"]["value"]


@router.get("/object", summary="Object")
async def object_function(
    request: Request,
):
    object_item = ObjectItem(**request.path_params, **request.query_params)
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=object_item.classes
    )
    # ignore profile returned by ProfilesMediatypesInfo for now - there is no 'hierarchy' among prez flavours' profiles
    # at present, the behaviour for which should be chosen (or if one should be chosen at all) has not been defined.
    object_item.selected_class = None
    endpoint_to_relations = get_endpoint_info_for_classes(object_item.classes)

    relationship_query = generate_relationship_query(
        object_item.uri, endpoint_to_relations
    )
    item_query = generate_item_construct(object_item, PREZ["profile/open"])
    item_graph, tabular_results = await send_queries(
        rdf_queries=[item_query], tabular_queries=[relationship_query]
    )
    # construct the system endpoint links
    internal_links_graph = generate_system_links(tabular_results[0], object_item.uri)
    return await return_from_graph(
        item_graph + internal_links_graph,
        prof_and_mt_info.mediatype,
        PREZ["profile/open"],
        prof_and_mt_info.profile_headers,
    )


# TODO add to readme:
# get classes from remote endpoint
# get endpoints which deliver classes & endpoint templates & parent relations for endpoints (from local prez graph)
# in parallel:
#   get parent uris from remote endpoint
#   get object information using open profile from remote endpoint
# construct the system links using the parent uris from the remote endpoint.
# merge the response with the system links


def get_endpoint_info_for_classes(classes) -> dict:
    """
    Queries Prez's in memory reference data for endpoints to determine which endpoints are relevant for the classes an
    object has, along with information about "parent" objects included in the URL path for the object. This information
    is whether the relationship in RDF is expected to be from the parent to the child, or from the child to the parent,
    and the predicate used for the relationship.
    """
    endpoint_query = get_endpoint_template_queries(classes)
    results = endpoints_graph_cache.query(endpoint_query)
    endpoint_to_relations = {}
    for result in results.bindings:
        endpoint_template = result["endpointTemplate"]
        relation = result["relation"]
        direction = result["direction"]
        if endpoint_template not in endpoint_to_relations:
            endpoint_to_relations[endpoint_template] = [(relation, direction)]
        else:
            endpoint_to_relations[endpoint_template].append((relation, direction))
    return endpoint_to_relations


def generate_system_links(relationship_results: list, object_uri: str) -> Graph:
    internal_links_graph = Graph()
    endpoints = []
    for endpoint_results in relationship_results:
        endpoint_template = Template(endpoint_results["endpoint"]["value"])
        template_args = {
            k: get_curie_id_for_uri(v["value"])
            for k, v in endpoint_results.items()
            if k != "endpoint"
        } | {"object": get_curie_id_for_uri(object_uri)}
        endpoints.append(endpoint_template.substitute(template_args))
    for endpoint in endpoints:
        internal_links_graph.add(
            (
                URIRef(object_uri),
                PREZ["link"],
                Literal(endpoint),
            )
        )
    return internal_links_graph
