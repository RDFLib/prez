import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import DCAT, RDF

from prez.reference_data.prez_ns import PREZ


@pytest.fixture()
def a_catalog_link(client):
    # get link for first catalog
    r = client.get("/catalogs")
    g = Graph().parse(data=r.text)
    member_uri = g.value(None, RDF.type, DCAT.Catalog)
    link = g.value(member_uri, URIRef("https://prez.dev/link", None))
    return link


@pytest.fixture()
def a_resource_link(client, a_catalog_link):
    r = client.get(a_catalog_link)
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef("https://prez.dev/link"))
    for link in links:
        if link != a_catalog_link:
            return link


def test_listing_alt_profile(client):
    r = client.get("/catalogs?_profile=altr-ext:alt-profile")
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("http://www.w3.org/ns/dx/connegp/altr-ext#alt-profile"),
        RDF.type,
        URIRef("https://prez.dev/ListingProfile"),
    ) in response_graph


def test_object_alt_profile_token(client, a_catalog_link):
    r = client.get(f"{a_catalog_link}?_mediatype=text/turtle&_profile=alt")
    response_graph = Graph().parse(data=r.text)
    object_profiles = (
        None,
        RDF.type,
        PREZ.ObjectProfile,
    )
    listing_profiles = (
        None,
        RDF.type,
        PREZ.ListingProfile,
    )
    assert len(list(response_graph.triples(object_profiles))) > 1
    assert (
        len(list(response_graph.triples(listing_profiles))) == 1
    )  # only the alt profile
