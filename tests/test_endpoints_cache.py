from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph

from prez.app import app
from prez.dependencies import get_query_sender
from prez.sparql.methods import Repo, PyoxigraphRepo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../tests/data/*/input/*.ttl"):
        store.load(file.read_bytes(), "text/turtle")

    return store


@pytest.fixture(scope="session")
def test_query_sender(test_store: Store) -> Repo:
    # Create a PyoxigraphQuerySender using the test_store
    return PyoxigraphRepo(test_store)


@pytest.fixture(scope="session")
def test_client(test_query_sender: Repo) -> TestClient:
    # Override the dependency to use the test_query_sender
    def override_get_query_sender():
        return test_query_sender

    app.dependency_overrides[get_query_sender] = override_get_query_sender

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


def test_reset_cache(test_client):
    test_client.get("/reset-tbox-cache")
    r = test_client.get("/tbox-cache")
    g = Graph().parse(data=r.text)
    assert len(g) > 6000  # cache expands as tests are run


def test_cache(test_client):
    r = test_client.get("/tbox-cache")
    g = Graph().parse(data=r.text)
    assert len(g) > 6000  # cache expands as tests are run
