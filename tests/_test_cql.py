import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store

from prez.app import app
from prez.dependencies import get_repo
from prez.sparql.methods import Repo, PyoxigraphRepo
from urllib.parse import quote_plus


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


@pytest.mark.parametrize(
    "cql_json_filename",
    [
        "example01.json",
        "example02.json",
        "example03.json",
        "example05a.json",
        "example05b.json",
        "example06b.json",
        "example09.json",
        "example10.json",
        "example11.json",
        "example12.json",
        "example14.json",
        "example15.json",
        "example17.json",
        "example29.json",
        "example31.json",
        "example32.json",
        "example33.json",
        "example34.json",
        "example35.json",
        "example39.json",
    ],
)
def test_simple(client, cql_json_filename):
    cql_json = Path(__file__).parent / f"data/cql/input/{cql_json_filename}"
    cql_json_as_json = json.loads(cql_json.read_text())
    headers = {"content-type": "application/json"}
    response = client.post("/cql", json=cql_json_as_json, headers=headers)
    assert response.status_code == 200


def test_intersects_post(client):
    cql_json = Path(__file__).parent / f"data/cql/input/geo_intersects.json"
    cql_json_as_json = json.loads(cql_json.read_text())
    headers = {"content-type": "application/json"}
    response = client.post("/cql", json=cql_json_as_json, headers=headers)
    assert response.status_code == 200


def test_intersects_get(client):
    cql_json = Path(__file__).parent / f"data/cql/input/geo_intersects.json"
    cql_json_as_json = json.loads(cql_json.read_text())
    query_string = quote_plus(json.dumps(cql_json_as_json))
    response = client.get(
        f"/cql?filter={query_string}&_mediatype=application/sparql-query"
    )
    assert response.status_code == 200
