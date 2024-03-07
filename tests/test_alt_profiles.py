import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, DCAT

from prez.app import app
from prez.dependencies import get_repo
from prez.repositories import Repo, PyoxigraphRepo


@pytest.fixture(scope="session")
def a_catalog_link(client):
    # get link for first catalog
    r = client.get("/catalogs")
    g = Graph().parse(data=r.text)
    member_uri = g.value(None, RDF.type, DCAT.Catalog)
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture(scope="session")
def a_resource_link(client, a_catalog_link):
    r = client.get(a_catalog_link)
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != a_catalog_link:
            return link


def test_listing_alt_profile(client):
    r = client.get(f"/catalogs?_mediatype=text/turtle&_profile=altr-ext:alt-profile")
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"),
        RDF.type,
        URIRef("https://prez.dev/ListingProfile"),
    ) in response_graph


def test_object_alt_profile(client, a_catalog_link):
    r = client.get(
        f"{a_catalog_link}?_mediatype=text/turtle&_profile=altr-ext:alt-profile"
    )
    response_graph = Graph().parse(data=r.text)
    expected_response = (
        URIRef("https://example.com/TopLevelCatalog"),
        RDF.type,
        DCAT.Catalog,
    )
    assert next(response_graph.triples(expected_response))
