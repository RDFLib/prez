from rdflib import Graph, URIRef
from rdflib.namespace import RDF, GEO


def test_feature_collection(client):
    r = client.get(f"/object?uri=https://example.com/FeatureCollection&_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://example.com/FeatureCollection"),
        RDF.type,
        GEO.FeatureCollection,
    ) in response_graph


def test_feature(client):
    r = client.get(f"/object?uri=https://example.com/Feature1&_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://example.com/Feature1"),
        RDF.type,
        GEO.Feature,
    ) in response_graph
