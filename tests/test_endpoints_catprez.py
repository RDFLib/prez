from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, DCAT

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
def a_catalog_link(client):
    # get link for first catalog
    r = client.get("/c/catalogs")
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


# @pytest.mark.xfail(reason="passes locally - setting to xfail pending test changes to pyoxigraph")
def test_catalog_listing_anot(client):
    r = client.get(f"/c/catalogs?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/catprez/expected_responses/catalog_listing_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Missing:{(expected_graph - response_graph).serialize()}"
        f"Extra:{(response_graph - expected_graph).serialize()}"
    )


def test_catalog_anot(client, a_catalog_link):
    r = client.get(f"/c/catalogs/pd:democat?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/catprez/expected_responses/catalog_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Missing:{(expected_graph - response_graph).serialize()}"
        f"Extra:{(response_graph - expected_graph).serialize()}"
    )


def test_resource_listing_anot(client, a_catalog_link):
    r = client.get(
        f"{a_catalog_link}/resources?_mediatype=text/anot+turtle&ordering-pred=http://purl.org/dc/terms/title"
    )
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/catprez/expected_responses/resource_listing_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Missing:{(expected_graph - response_graph).serialize()}"
        f"Extra:{(response_graph - expected_graph).serialize()}"
    )


def test_resource_anot(client, a_resource_link):
    r = client.get(f"{a_resource_link}?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/catprez/expected_responses/resource_anot.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"Missing:{(expected_graph - response_graph).serialize()}"
        f"Extra:{(response_graph - expected_graph).serialize()}"
    )
