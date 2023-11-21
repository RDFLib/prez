from string import Template
from typing import FrozenSet

from rdflib import Graph, Literal, URIRef, DCTERMS

from prez.cache import endpoints_graph_cache, links_ids_graph_cache
from prez.reference_data.prez_ns import PREZ
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.model_methods import get_classes
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import (
    get_endpoint_template_queries,
    generate_relationship_query,
)


async def _add_prez_links(graph: Graph, repo):
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    uris = [uri for uri in graph.all_nodes() if isinstance(uri, URIRef)]
    for uri in uris:
        await _create_internal_links_graph(uri, graph, repo)


async def _create_internal_links_graph(uri, graph, repo: Repo):
    quads = list(
        links_ids_graph_cache.quads((None, None, None, uri))
    )  # context required as not all triples that relate to links or identifiers for a particular object have that object's URI as the subject
    if quads:
        for quad in quads:
            graph.add(quad[:3])
    else:
        klasses = await get_classes(uri, repo)
        for klass in klasses:
            endpoint_to_relations = get_endpoint_info_for_classes(frozenset([klass]))
            relationship_query = generate_relationship_query(uri, endpoint_to_relations)
            if relationship_query:
                _, tabular_results = await repo.send_queries(
                    [], [(uri, relationship_query)]
                )
                for _, result in tabular_results:
                    quads = generate_system_links_object(result, uri)
                    for quad in quads:
                        graph.add(quad[:3])  # just add the triple not the quad
                        links_ids_graph_cache.add(quad)  # add the quad to the cache


def get_endpoint_info_for_classes(classes: FrozenSet[URIRef]) -> dict:
    """
    Queries Prez's in memory reference data for endpoints to determine which endpoints are relevant for the classes an
    object has, along with information about "parent" objects included in the URL path for the object. This information
    is whether the relationship in RDF is expected to be from the parent to the child, or from the child to the parent,
    and the predicate used for the relationship.
    """
    endpoint_query = get_endpoint_template_queries(classes)
    results = endpoints_graph_cache.query(endpoint_query)
    endpoint_to_relations = {}
    if results.bindings != [{}]:
        for result in results.bindings:
            endpoint_template = result["endpoint_template"]
            relation = result.get("relation_predicate")
            direction = result.get("relation_direction")
            if endpoint_template not in endpoint_to_relations:
                endpoint_to_relations[endpoint_template] = [(relation, direction)]
            else:
                endpoint_to_relations[endpoint_template].append((relation, direction))
    return endpoint_to_relations


def generate_system_links_object(relationship_results: list, object_uri: str):
    """
    Generates system links for objects from the 'object' endpoint
    relationship_results: a list of dictionaries, one per endpoint, each dictionary contains:
    1. an endpoint template with parameters denoted by `$` to be populated using python's string Template library
    2. the arguments to populate this endpoint template, as URIs. The get_curie_id_for_uri function is used to convert
    these to curies.
    """
    endpoints = []
    link_quads = []
    for endpoint_results in relationship_results:
        endpoint_template = Template(endpoint_results["endpoint"]["value"])
        template_args = {
            k: get_curie_id_for_uri(v["value"])
            for k, v in endpoint_results.items()
            if k != "endpoint"
        } | {"object": get_curie_id_for_uri(URIRef(object_uri))}
        endpoints.append(endpoint_template.substitute(template_args))
    for endpoint in endpoints:
        link_quads.append(
            (URIRef(object_uri), PREZ["link"], Literal(endpoint), object_uri)
        )
    for ep_result in relationship_results:
        for k, v in ep_result.items():
            if k != "endpoint":
                uri = URIRef(v["value"])
                curie = get_curie_id_for_uri(uri)
                link_quads.append(
                    (
                        uri,
                        DCTERMS.identifier,
                        Literal(curie, datatype=PREZ.identifier),
                        object_uri,
                    )
                )
    object_curie = get_curie_id_for_uri(object_uri)
    link_quads.append(
        (
            object_uri,
            DCTERMS.identifier,
            Literal(object_curie, datatype=PREZ.identifier),
            object_uri,
        )
    )
    return link_quads
