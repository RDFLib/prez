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


def get_curie(test_client: TestClient, iri: str) -> str:
    response = test_client.get(f"/identifier/curie/{iri}")
    if response.status_code != 200:
        raise ValueError(f"Failed to retrieve curie for {iri}. {response.text}")
    return response.text


@pytest.mark.parametrize(
    "iri, inbound, outbound, count",
    [
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            "http://www.w3.org/2004/02/skos/core#inScheme",
            None,
            0,
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose-no-children",
            "http://www.w3.org/2004/02/skos/core#inScheme",
            None,
            0,
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            None,
            "http://www.w3.org/2004/02/skos/core#hasTopConcept",
            0,
        ],
    ],
)
def test_count(
    test_client: TestClient,
    iri: str,
    inbound: str | None,
    outbound: str | None,
    count: int,
):
    curie = get_curie(test_client, iri)
    params = {"curie": curie, "inbound": inbound, "outbound": outbound}
    response = test_client.get(f"/count", params=params)
    assert int(response.text) == count
