import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, GEO

from prez.app import app
from prez.dependencies import get_repo
from prez.repositories import Repo, PyoxigraphRepo


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
def test_client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app, backend_options={"loop_factory": asyncio.new_event_loop}) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


def test_feature_collection(test_client):
    r = test_client.get(f"/object?uri=https://test/feature-collection")
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://test/feature-collection"),
        RDF.type,
        GEO.FeatureCollection,
    ) in response_graph


def test_feature(test_client):
    r = test_client.get(
        f"/object?uri=https://linked.data.gov.au/datasets/geofabric/hydroid/102208962"
    )
    response_graph = Graph().parse(data=r.text)
    assert (
        URIRef("https://linked.data.gov.au/datasets/geofabric/hydroid/102208962"),
        RDF.type,
        GEO.Feature,
    ) in response_graph
