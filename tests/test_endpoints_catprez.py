from rdflib import Graph, URIRef
from rdflib.namespace import RDF, DCAT


def test_catalog_listing_anot(client):
    r = client.get(f"/catalogs?_mediatype=text/turtle&_profile=prez:OGCListingProfile")
    response_graph = Graph().parse(data=r.text)
    expected_response_1 = (
        URIRef("https://example.com/CatalogOne"),
        RDF.type,
        DCAT.Catalog,
    )
    expected_response_2 = (
        URIRef("https://example.com/CatalogTwo"),
        RDF.type,
        DCAT.Catalog,
    )
    assert next(response_graph.triples(expected_response_1))
    assert next(response_graph.triples(expected_response_2))


def test_catalog_anot(client, a_catprez_catalog_link):
    r = client.get(f"{a_catprez_catalog_link}?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    expected_response = (
        URIRef("https://example.com/CatalogOne"),
        RDF.type,
        DCAT.Catalog,
    )
    assert next(response_graph.triples(expected_response))


def test_lower_level_listing_anot(client, a_catprez_catalog_link):
    r = client.get(f"{a_catprez_catalog_link}/collections?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    expected_response = (
        URIRef("https://example.com/DCATResource"),
        RDF.type,
        DCAT.Resource,
    )
    assert next(response_graph.triples(expected_response))
