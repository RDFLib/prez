from prez.services.query_generation.node_selection.endpoint_shacl import (
    NodeShape,
    PropertyShape,
)
from rdflib import Graph, URIRef
import pytest

endpoints_graph = Graph().parse(
    "prez/reference_data/endpoints/endpoint_node_selection_shapes.ttl", format="turtle"
)


# @pytest.fixture
# def property_shape():
#     return endpoints_graph.value(
#         subject=URIRef("http://example.org/ns#ResourceListing"),
#         predicate=URIRef("http://www.w3.org/ns/shacl#property"),
#     )


@pytest.mark.parametrize(
    "nodeshape_uri", ["http://example.org/ns#FeatureCollectionListing"]
)
def test_nodeshape_parsing(nodeshape_uri):
    ns = NodeShape(uri=URIRef(nodeshape_uri), graph=endpoints_graph)
    assert ns.targetClasses == [
        URIRef("http://www.opengis.net/ont/geosparql#FeatureCollection")
    ]
    assert len(ns.propertyShapesURIs) == 1


@pytest.mark.parametrize(
    "nodeshape_uri",
    [
        "http://example.org/ns#TopLevelCatalogs"
        # "http://example.org/ns#FeatureListing"
    ],
)
def test_nodeshape_to_grammar(nodeshape_uri):
    ns = NodeShape(uri=URIRef(nodeshape_uri), graph=endpoints_graph)
    ns.to_grammar()
    print("")


@pytest.mark.parametrize(
    "property_shape", ["http://example.org/ns#resourceListingPropertyShape2"]
)
def test_propertyshape_parsing(property_shape):
    ps = PropertyShape(uri=URIRef(property_shape), graph=endpoints_graph)
    ps.to_grammar()
    print("")


@pytest.mark.parametrize(
    "property_shape", ["http://example.org/ns#resourceListingPropertyShape2"]
)
def test_propertyshape_create_grammar(property_shape):
    ps = PropertyShape(uri=URIRef(property_shape))
    # ps.from_graph(graph=endpoints_graph)
    # ps.to_grammar()
    # assert True
