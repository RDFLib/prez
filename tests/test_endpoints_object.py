from rdflib import Graph, URIRef
from rdflib.namespace import GEO, RDF


def test_feature_collection(client):
    r = client.get(
        "/object?uri=https://example.com/spaceprez/FeatureCollection&_mediatype=text/turtle"
    )
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://example.com/spaceprez/FeatureCollection"),
        RDF.type,
        GEO.FeatureCollection,
    ) in response_graph


def test_feature(client):
    r = client.get(
        "/object?uri=https://example.com/spaceprez/Feature1&_mediatype=text/turtle"
    )
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://example.com/spaceprez/Feature1"),
        RDF.type,
        GEO.Feature,
    ) in response_graph
