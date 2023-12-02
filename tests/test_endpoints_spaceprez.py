from rdflib import Graph, URIRef
from rdflib.namespace import RDF, DCAT, GEO


def test_dataset_anot(client, a_spaceprez_catalog_link):
    r = client.get(f"{a_spaceprez_catalog_link}?_mediatype=text/turtle")
    g_text = r.text
    response_graph = Graph().parse(data=g_text)
    expected_response_1 = (
        URIRef("https://example.com/SpacePrezCatalog"),
        RDF.type,
        DCAT.Catalog,
    )
    assert next(response_graph.triples(expected_response_1))


def test_feature_collection(client, an_fc_link):
    r = client.get(f"{an_fc_link}?_mediatype=text/turtle")
    g_text = r.text
    response_graph = Graph().parse(data=g_text)
    assert (
        URIRef("https://example.com/FeatureCollection"),
        RDF.type,
        GEO.FeatureCollection,
    ) in response_graph


def test_feature(client, a_feature_link):
    r = client.get(f"{a_feature_link}?_mediatype=text/turtle")
    g_text = r.text
    response_graph = Graph().parse(data=g_text)
    expected_response_1 = (
        URIRef("https://example.com/Feature1"),
        RDF.type,
        GEO.Feature,
    )
    assert next(response_graph.triples(expected_response_1))


def test_feature_listing_anot(client, an_fc_link):
    r = client.get(f"{an_fc_link}/items?_mediatype=text/turtle")
    g_text = r.text
    response_graph = Graph().parse(data=g_text)
    expected_response_1 = (
        URIRef("https://example.com/Feature1"),
        RDF.type,
        GEO.Feature,
    )
    expected_response_2 = (
        URIRef("https://example.com/Feature2"),
        RDF.type,
        GEO.Feature,
    )
    assert next(response_graph.triples(expected_response_1))
    assert next(response_graph.triples(expected_response_2))
