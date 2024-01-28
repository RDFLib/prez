import logging
import time
from string import Template
from typing import FrozenSet

from fastapi import Depends
from rdflib import Graph, Literal, URIRef, DCTERMS, BNode
from rdflib.namespace import SH

from prez.cache import endpoints_graph_cache, links_ids_graph_cache
from prez.dependencies import get_system_repo
from prez.reference_data.prez_ns import PREZ
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.model_methods import get_classes
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import (
    get_endpoint_template_queries,
    generate_relationship_query,
)
from temp.shacl2sparql import ONT

log = logging.getLogger(__name__)


async def _add_prez_link_to_collection_page(
    item_graph: Graph, item_uri: URIRef, request_url: str, endpoint_uri: URIRef
):
    """
    1. get the request's URL; this will be the URL of the current object page
    2. look up the endpoint that hasParentEndpoint the object endpoint in the endpoints graph cache
    3. take the fragment (suffix) of the endpoint template for the child endpoint identified in step 2
    4. append the fragment to the URL from step 1
    """
    child_endpoint = endpoints_graph_cache.value(
        predicate=ONT.parentEndpoint, object=endpoint_uri
    )
    child_endpoint_template = endpoints_graph_cache.value(
        subject=child_endpoint, predicate=ONT.endpointTemplate
    )
    if child_endpoint_template:
        last_part_of_url = child_endpoint_template.split("/")[-1]
        collections_url = f"{request_url}/{last_part_of_url}"
        bnode = BNode()
        item_graph.add((item_uri, PREZ.members, bnode))
        item_graph.add((bnode, PREZ.link, Literal(collections_url)))


async def _add_prez_links(graph: Graph, repo: Repo, system_repo: Repo):
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    uris = [uri for uri in graph.all_nodes() if isinstance(uri, URIRef)]
    uri_to_klasses = {}
    for uri in uris:
        uri_to_klasses[uri] = await get_classes(uri, repo)

    for uri, klasses in uri_to_klasses.items():
        await _new_link_generation(uri, repo, klasses, system_repo)
        # await _create_internal_links_graph(uri, graph, repo, klasses, system_repo)

async def _new_link_generation(uri, repo: Repo, klasses, system_repo):
    # get the endpoints that can deliver the class
    # many node shapes to one endpoint; multiple node shapes can point to the endpoint
    query = f"""SELECT ?nodeShape {{ ?nodeShape a {SH.NodeShape} ;
                                        {SH.targetClass} ?klasses .
                                    VALUES ?klasses {" ".join(["<" + klass.n3() + ">" for klass in klasses])} 
                                        }}"""
    {" ".join(["<" + klass.n3() + ">" for klass in klasses])}
    system_repo.send_queries()
    # if there's a link generation query for the endpoint, run it

    _, tabular_results = await repo.send_queries([], [(None, query)])


async def _create_internal_links_graph(uri, graph, repo: Repo, klasses, system_repo):
    quads = list(
        links_ids_graph_cache.quads((None, None, None, uri))
    )  # context required as not all triples that relate to links or identifiers for a particular object have that object's URI as the subject
    if quads:
        for quad in quads:
            graph.add(quad[:3])
    else:
        for klass in klasses:
            endpoint_to_relations = await get_endpoint_info_for_classes(
                frozenset([klass]), system_repo
            )
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


async def get_endpoint_info_for_classes(
    classes: FrozenSet[URIRef], system_repo
) -> dict:
    """
    Queries Prez's in memory reference data for endpoints to determine which endpoints are relevant for the classes an
    object has, along with information about "parent" objects included in the URL path for the object. This information
    is whether the relationship in RDF is expected to be from the parent to the child, or from the child to the parent,
    and the predicate used for the relationship.
    """
    endpoint_query = get_endpoint_template_queries(classes)
    results = await system_repo.send_queries([], [(None, endpoint_query)])
    endpoint_to_relations = {}
    if results[1][0][1] != [{}]:
        for result in results[1][0][1]:
            endpoint_template = result["endpoint_template"]["value"]
            relation = result.get("relation_predicate")
            if relation:
                relation = URIRef(relation["value"])
            direction = result.get("relation_direction")
            if direction:
                direction = URIRef(direction["value"])
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
