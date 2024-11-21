from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.namespace import DCAT, RDF

from prez.app import assemble_app
from prez.dependencies import get_data_repo
from prez.repositories import PyoxigraphRepo, Repo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../tests/data/prefixes/*.ttl"):
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

    app.dependency_overrides[get_data_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.mark.xfail(
    reason="Dependency overrides not configured correctly. Test passes when manually tested using Fuseki"
)
def test_catalog_link(client):
    # get link for first catalog
    r = client.get("/c/catalogs")
    g = Graph().parse(data=r.text)
    member_uri = g.value(None, RDF.type, DCAT.Catalog)
    link = str(g.value(member_uri, URIRef("https://prez.dev/link", None)))
    assert link == "/c/catalogs/davo:bogusCatalogous"
