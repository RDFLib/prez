import pytest
from rdflib import Graph, URIRef

from prez.services.query_generation.shacl import (
    NodeShape,
)
from sparql_grammar_pydantic import Var

endpoints_graph = Graph().parse(
    "prez/reference_data/endpoints/endpoint_nodeshapes.ttl", format="turtle"
)


@pytest.mark.parametrize("nodeshape_uri", ["http://example.org/ns#Collections"])
def test_nodeshape_parsing(nodeshape_uri):
    ns = NodeShape(
        uri=URIRef(nodeshape_uri),
        graph=endpoints_graph,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
    )
    assert ns.targetClasses == [
        URIRef("http://www.w3.org/2004/02/skos/core#ConceptScheme"),
        URIRef("http://www.w3.org/2004/02/skos/core#Collection"),
        URIRef("http://www.w3.org/ns/dcat#Resource"),
        URIRef("http://www.w3.org/ns/dcat#Dataset")
    ]
    assert len(ns.propertyShapesURIs) == 1


@pytest.mark.parametrize(
    "nodeshape_uri",
    ["http://example.org/ns#ConceptSchemeConcept"],
)
def test_nodeshape_to_grammar(nodeshape_uri):
    ns = NodeShape(
        uri=URIRef(nodeshape_uri),
        graph=endpoints_graph,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
    )
    ...
