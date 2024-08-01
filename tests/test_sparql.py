from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store

from prez.app import assemble_app
from prez.dependencies import get_repo
from prez.sparql.methods import PyoxigraphRepo, Repo


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

    app = assemble_app()

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


def test_select(client):
    """check that a valid select query returns a 200 response."""
    r = client.get(
        "/sparql?query=SELECT%20*%0AWHERE%20%7B%0A%20%20%3Fs%20%3Fp%20%3Fo%0A%7D%20LIMIT%201"
    )
    assert r.status_code, 200


def test_construct(client):
    """check that a valid construct query returns a 200 response."""
    r = client.get(
        "/sparql?query=CONSTRUCT%20%7B%0A%20%20%3Fs%20%3Fp%20%3Fo%0A%7D%20WHERE%20%7B%0A%20%20%3Fs%20%3Fp%20%3Fo%0A%7D%20LIMIT%201"
    )
    assert r.status_code, 200


def test_ask(client):
    """check that a valid ask query returns a 200 response."""
    r = client.get(
        "/sparql?query=PREFIX%20ex%3A%20%3Chttp%3A%2F%2Fexample.com%2Fdatasets%2F%3E%0APREFIX%20dcterms%3A%20%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Fterms%2F%3E%0A%0AASK%0AWHERE%20%7B%0A%20%20%3Fsubject%20dcterms%3Atitle%20%3Ftitle%20.%0A%20%20FILTER%20CONTAINS(LCASE(%3Ftitle)%2C%20%22sandgate%22)%0A%7D"
    )
    assert r.status_code, 200


def test_post(client):
    """check that a valid post query returns a 200 response."""
    r = client.post(
        "/sparql",
        data={
            "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1",
            "format": "application/x-www-form-urlencoded",
        },
    )
    assert r.status_code, 200


def test_post_invalid_data(client):
    """check that a post query with invalid data returns a 400 response."""
    r = client.post(
        "/sparql",
        data={
            "query": "INVALID QUERY",
            "format": "application/x-www-form-urlencoded",
        },
    )
    assert r.status_code == 400


def test_insert_as_query(client):
    """
    Also tested manually with Fuseki
    """
    r = client.post(
        "/sparql",
        data={
            "query": "INSERT {<:s> <:p> <:o>}",
            "format": "application/x-www-form-urlencoded",
        },
    )
    assert r.status_code == 400
