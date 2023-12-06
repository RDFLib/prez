import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, DCAT
from rdflib.compare import isomorphic

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


def wait_for_app_to_be_ready(client, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = client.get("/health")
            if response.status_code == 200:
                return
        except Exception as e:
            print(e)
        time.sleep(0.5)
    raise RuntimeError("App did not start within the specified timeout")


@pytest.fixture(scope="session")
def client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        wait_for_app_to_be_ready(c)
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


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


def test_catalog_listing_anot(client):
    r = client.get(
        f"/catalogs?_mediatype=text/anot+turtle&_profile=prez:OGCListingProfile"
    )
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/catprez/expected_responses/top_level_catalog_listing_anot.ttl"
    )
    assert isomorphic(response_graph, expected_graph), print(
        f"RESPONSE GRAPH\n{response_graph.serialize()},"
        f"EXPECTED GRAPH\n{expected_graph.serialize()}",
        f"MISSING TRIPLES\n{(expected_graph - response_graph).serialize()}",
        f"EXTRA TRIPLES\n{(response_graph - expected_graph).serialize()}",
    )


def test_catalog_anot(client, a_catalog_link):
    r = client.get(f"{a_catalog_link}?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/catprez/expected_responses/top_level_catalog_anot.ttl"
    )
    assert isomorphic(response_graph, expected_graph), print(
        f"RESPONSE GRAPH\n{response_graph.serialize()},"
        f"EXPECTED GRAPH\n{expected_graph.serialize()}",
        f"MISSING TRIPLES\n{(expected_graph - response_graph).serialize()}",
        f"EXTRA TRIPLES\n{(response_graph - expected_graph).serialize()}",
    )


def test_resource_listing_anot(client, a_catalog_link):
    r = client.get(f"{a_catalog_link}/collections?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/catprez/expected_responses/resource_listing_anot.ttl"
    )
    assert isomorphic(response_graph, expected_graph), print(
        f"RESPONSE GRAPH\n{response_graph.serialize()},"
        f"EXPECTED GRAPH\n{expected_graph.serialize()}",
        f"MISSING TRIPLES\n{(expected_graph - response_graph).serialize()}",
        f"EXTRA TRIPLES\n{(response_graph - expected_graph).serialize()}",
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
