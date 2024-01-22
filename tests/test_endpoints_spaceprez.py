from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF, DCAT, RDFS, GEO

from prez.app import app
from prez.dependencies import get_repo
from prez.sparql.methods import Repo, PyoxigraphRepo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../test_data/spaceprez.ttl"):
        store.load(file.read_bytes(), "text/turtle")

    return store


@pytest.fixture(scope="session")
def test_repo(test_store: Store) -> Repo:
    # Create a PyoxigraphQuerySender using the test_store
    return PyoxigraphRepo(test_store)


@pytest.fixture(scope="session")
def client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def a_dataset_link(client):
    r = client.get("/s/catalogs")
    g = Graph().parse(data=r.text)
    member_uri = g.value(None, RDF.type, DCAT.Dataset)
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture(scope="session")
def an_fc_link(client, a_dataset_link):
    r = client.get(f"{a_dataset_link}/collections")
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != a_dataset_link:
            return link


@pytest.fixture(scope="session")
def a_feature_link(client, an_fc_link):
    r = client.get(f"{an_fc_link}/items")
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != an_fc_link:
            return link


def test_dataset_anot(client, a_dataset_link):
    r = client.get(f"{a_dataset_link}?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    expected_response_1 = (
        URIRef("https://example.com/Dataset"),
        RDF.type,
        DCAT.Dataset,
    )
    assert next(response_graph.triples(expected_response_1))



def test_feature_collection(client, an_fc_link):
    r = client.get(f"{an_fc_link}?_mediatype=text/turtle")
    response_graph = Graph().parse(data=r.text)
    expected_response_1 = (
        URIRef("https://example.com/FeatureCollection"),
        RDF.type,
        GEO.FeatureCollection,
    )
    assert next(response_graph.triples(expected_response_1))

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