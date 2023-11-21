from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, DCAT, RDFS

from prez.app import app
from prez.dependencies import get_repo
from prez.sparql.methods import Repo, PyoxigraphRepo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../tests/data/*/input/*.ttl"):
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
    r = client.get("/s/datasets")
    g = Graph().parse(data=r.text)
    member_uri = g.value(None, RDF.type, DCAT.Dataset)
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture(scope="session")
def an_fc_link(client, a_dataset_link):
    r = client.get(f"{a_dataset_link}/collections")
    g = Graph().parse(data=r.text)
    member_uri = g.value(
        URIRef("http://example.com/datasets/sandgate"), RDFS.member, None
    )
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture(scope="session")
def a_feature_link(client, an_fc_link):
    r = client.get(f"{an_fc_link}/items")
    g = Graph().parse(data=r.text)
    member_uri = g.value(
        URIRef("http://example.com/datasets/sandgate/catchments"), RDFS.member, None
    )
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


def test_dataset_anot(client, a_dataset_link):
    r = client.get(f"{a_dataset_link}?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/spaceprez/expected_responses/dataset_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Graph delta:{(expected_graph - response_graph).serialize()}"
    )


def test_feature_collection_anot(client, an_fc_link):
    r = client.get(f"{an_fc_link}?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/spaceprez/expected_responses/feature_collection_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Graph delta:{(expected_graph - response_graph).serialize()}"
    )


def test_feature_anot(client, a_feature_link):
    r = client.get(f"{a_feature_link}?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/spaceprez/expected_responses/feature_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Graph delta:{(expected_graph - response_graph).serialize()}"
    )


def test_dataset_listing_anot(client):
    r = client.get("/s/datasets?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/spaceprez/expected_responses/dataset_listing_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Graph delta:{(expected_graph - response_graph).serialize()}"
    )


def test_feature_collection_listing_anot(client, a_dataset_link):
    r = client.get(f"{a_dataset_link}/collections?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/spaceprez/expected_responses/feature_collection_listing_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Graph delta:{(expected_graph - response_graph).serialize()}"
    )


def test_feature_listing_anot(client, an_fc_link):
    r = client.get(f"{an_fc_link}/items?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/spaceprez/expected_responses/feature_listing_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Graph delta:{(expected_graph - response_graph).serialize()}"
    )
