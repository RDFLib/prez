"""test_pmt_headers

A set of tests to confirm that the Profile and Media Type information in the response headers are
as expected for object and listing endpoints.

Also checks the content-disposition header
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store

from prez.app import assemble_app
from prez.dependencies import get_repo
from prez.services.curie_functions import get_curie_id_for_uri
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
def test_client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app = assemble_app()

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "endpoint, mediatype, filename",
    [
        ("/v/vocab", "text/turtle", "SchemesList"),
        ("/s/datasets", "text/turtle", "DatasetList"),
        ("/c/catalogs", "text/turtle", "CatalogList"),
        ("/v/vocab", "application/ld+json", "SchemesList"),
        ("/s/datasets", "application/ld+json", "DatasetList"),
        ("/c/catalogs", "application/ld+json", "CatalogList"),
    ],
)
def test_listing_endpoint(
    endpoint: str, mediatype: str, filename: str, test_client: TestClient
):
    """Assert that response headers are returned correctly for a listing endpoint.

    i.e that they specify the

      - Content-Type, and
      - Content-Disposition.

    headers. And that the headers have an appropriate value.
    """
    headers = {"accept": mediatype}
    expected_headers = {
        "content-type": mediatype,
        "content-disposition": f"inline; filename={filename}",
    }
    response = test_client.get(endpoint, headers=headers)
    assert all(
        header in response.headers.keys() for header in expected_headers.keys()
    ), f"Response must specify the {expected_headers.keys()} headers."
    assert all(
        response.headers[header] == expected_headers[header]
        for header in expected_headers.keys()
    ), "Required headers do not have the expected values."


@pytest.mark.parametrize(
    "endpoint, mediatype, object_uri",
    [
        ("/v/vocab", "text/turtle", "https://linked.data.gov.au/def/vocdermods"),
        ("/s/datasets", "text/turtle", "http://example.com/datasets/sandgate"),
        ("/c/catalogs", "text/turtle", "https://data.idnau.org/pid/democat"),
        (
            "/v/vocab",
            "application/ld+json",
            "https://linked.data.gov.au/def/vocdermods",
        ),
        ("/s/datasets", "application/ld+json", "http://example.com/datasets/sandgate"),
        ("/c/catalogs", "application/ld+json", "https://data.idnau.org/pid/democat"),
    ],
)
def test_object_endpoint(
    endpoint: str, mediatype: str, object_uri: str, test_client: TestClient
):
    """Assert that response headers are returned correctly for an object endpoint.

    i.e that they specify the

      - Content-Type, and
      - Content-Disposition.

    headers. And that the headers have an appropriate value.
    """
    curie = get_curie_id_for_uri(object_uri)
    headers = {"accept": mediatype}
    expected_headers = {
        "content-type": mediatype,
        "content-disposition": f"inline; filename={curie}",
    }
    response = test_client.get(endpoint + "/" + curie, headers=headers)
    assert all(
        header in response.headers.keys() for header in expected_headers.keys()
    ), f"Response must specify the {expected_headers.keys()} headers."
    assert all(
        response.headers[header] == expected_headers[header]
        for header in expected_headers.keys()
    ), "Required headers do not have the expected values."
