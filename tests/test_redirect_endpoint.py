from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store

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


@pytest.mark.parametrize(
    "iri, url, expected_response_code, accept_header_value",
    [
        [
            "http://data.bgs.ac.uk/id/dataHolding/13603129",
            "http://metadata.bgs.ac.uk/geonetwork/srv/eng/catalog.search#/metadata/9df8df53-2a1d-37a8-e044-0003ba9b0d98",
            307,
            "",
        ],
        ["http://example.com/non-existent", None, 404, ""],
        [
            "http://data.bgs.ac.uk/id/dataHolding/13603129",
            "http://metadata.bgs.ac.uk/geonetwork/srv/eng/catalog.search#/metadata/9df8df53-2a1d-37a8-e044-0003ba9b0d98",
            307,
            "text/turtle",
        ],
    ],
)
def test_redirect_endpoint(
    test_client: TestClient,
    iri: str,
    url: str,
    expected_response_code,
    accept_header_value: str | None,
):
    params = {"iri": iri}
    headers = {"accept": accept_header_value}
    response = test_client.get(
        "/identifier/redirect", params=params, headers=headers, follow_redirects=False
    )

    if expected_response_code != 404:
        assert response.status_code == expected_response_code
        assert response.headers.get("location") == url

        if accept_header_value:
            assert response.headers.get("accept") == accept_header_value
    else:
        assert response.status_code == expected_response_code
        assert response.headers.get("content-type") == "application/json"
        data = response.json()
        assert data.get("status_code") == expected_response_code
        assert data.get("detail") == f"No homepage found for IRI {iri}."
