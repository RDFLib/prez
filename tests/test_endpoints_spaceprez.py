import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, DCAT, GEO


@pytest.fixture(scope="session")
def a_catalog_link(client):
    r = client.get("/catalogs")
    g = Graph().parse(data=r.text)
    member_uri = URIRef("https://example.com/SpacePrezCatalog")
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture(scope="session")
def an_fc_link(client, a_catalog_link):
    r = client.get(f"{a_catalog_link}/collections")
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != a_catalog_link:
            return link


@pytest.fixture(scope="session")
def a_feature_link(client, an_fc_link):
    r = client.get(f"{an_fc_link}/items")
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != an_fc_link:
            return link


def test_dataset_anot(client, a_catalog_link):
    r = client.get(f"{a_catalog_link}?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    expected_response_1 = (
        URIRef("https://example.com/SpacePrezCatalog"),
        RDF.type,
        DCAT.Catalog,
    )
    assert next(response_graph.triples(expected_response_1))


def test_feature_collection(client, an_fc_link):
    r = client.get(f"{an_fc_link}?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://example.com/FeatureCollection"),
        RDF.type,
        GEO.FeatureCollection,
    ) in response_graph


def test_feature(client, a_feature_link):
    r = client.get(f"{a_feature_link}?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    expected_response_1 = (
        URIRef("https://example.com/Feature1"),
        RDF.type,
        GEO.Feature,
    )
    assert next(response_graph.triples(expected_response_1))


def test_feature_listing_anot(client, an_fc_link):
    r = client.get(f"{an_fc_link}/items?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
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
