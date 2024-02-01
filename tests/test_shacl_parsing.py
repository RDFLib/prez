from temp.shacl_nodeshapes2sparql import NodeShape, PropertyShape
from rdflib import Graph, URIRef
import pytest

endpoints_graph = Graph().parse("tests/data/nodeshapes/endpoints.ttl", format="turtle")


@pytest.fixture
def property_shape():
    return endpoints_graph.value(
        subject=URIRef("http://example.org/ns#FeatureCollectionListing"),
        predicate=URIRef("http://www.w3.org/ns/shacl#property"),
    )


@pytest.mark.parametrize("nodeshape_uri",
                         [
                             "http://example.org/ns#FeatureCollectionListing"
                         ])
def test_nodeshape_parsing(nodeshape_uri):
    ns = NodeShape(uri=URIRef(nodeshape_uri))
    ns.from_shacl_graph(endpoints_graph)
    assert ns.targetClass == [URIRef("http://www.opengis.net/ont/geosparql#FeatureCollection")]
    assert len(ns.propertyShapes) == 1


def test_propertyshape_parsing(property_shape):
    ps = PropertyShape(uri=property_shape)
    ps.from_graph(graph=endpoints_graph)
    print('')


def test_propertyshape_create_grammar(property_shape):
    ps = PropertyShape(uri=property_shape)
    ps.from_graph(graph=endpoints_graph)
    ps.to_grammar()
    assert True