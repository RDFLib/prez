from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph
from rdflib import RDF, DCAT

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
def test_client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def dataset_uri(test_client):
    # get link for first dataset
    r = test_client.get("/s/datasets")
    g = Graph().parse(data=r.text)
    return g.value(None, RDF.type, DCAT.Dataset)


def test_object_endpoint_sp_dataset(test_client, dataset_uri):
    r = test_client.get(f"/object?uri={dataset_uri}")
    assert r.status_code == 200


def test_feature_collection(test_client):
    r = test_client.get(f"/object?uri=https://test/feature-collection")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent / "../tests/data/object/expected_responses/fc.ttl"
    )
    assert response_graph.isomorphic(expected_graph), print(
        f"""Expected-Response:{(expected_graph - response_graph).serialize()}
            Response-Expected:{(expected_graph - response_graph).serialize()}"""
    )


def test_feature(test_client):
    r = test_client.get(
        f"/object?uri=https://linked.data.gov.au/datasets/geofabric/hydroid/102208962"
    )
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent / "../tests/data/object/expected_responses/feature.ttl"
    )
    assert response_graph.isomorphic(expected_graph)
