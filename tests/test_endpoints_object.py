from rdflib import Graph, URIRef
from rdflib.namespace import RDF, GEO


def test_feature_collection(client):
    r = client.get(f"/object?uri=https://test/feature-collection")
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://test/feature-collection"),
        RDF.type,
        GEO.FeatureCollection,
    ) in response_graph


def test_feature(client):
    r = client.get(
        f"/object?uri=https://linked.data.gov.au/datasets/geofabric/hydroid/102208962"
    )
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://linked.data.gov.au/datasets/geofabric/hydroid/102208962"),
        RDF.type,
        GEO.Feature,
    ) in response_graph
