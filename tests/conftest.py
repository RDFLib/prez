import os

from rdflib import Graph, URIRef

# comment / uncomment for the CQL tests - cannot figure out how to get a different conftest picked up.
os.environ["SPARQL_REPO_TYPE"] = "pyoxigraph"

# os.environ["SPARQL_ENDPOINT"] = "http://localhost:3030/dataset"
# os.environ["SPARQL_REPO_TYPE"] = "remote"

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store

from prez.app import assemble_app
from prez.dependencies import get_data_repo
from prez.repositories import Repo, PyoxigraphRepo


@pytest.fixture(scope="module")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../test_data/*.ttl"):
        store.load(file.read_bytes(), "text/turtle")

    return store


@pytest.fixture(scope="module")
def test_repo(test_store: Store) -> Repo:
    # Create a PyoxigraphQuerySender using the test_store
    return PyoxigraphRepo(test_store)


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def client_no_override() -> TestClient:

    app = assemble_app()

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def a_spaceprez_catalog_link(client):
    r = client.get("/catalogs")
    g = Graph().parse(data=r.text)
    member_uri = URIRef("https://example.com/SpacePrezCatalog")
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture()
def an_fc_link(client, a_spaceprez_catalog_link):
    r = client.get(f"{a_spaceprez_catalog_link}/collections")
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != a_spaceprez_catalog_link:
            return link


@pytest.fixture()
def a_feature_link(client, an_fc_link):
    r = client.get(f"{an_fc_link}/items")
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != an_fc_link:
            return link


@pytest.fixture()
def a_catprez_catalog_link(client):
    # get link for first catalog
    r = client.get("/catalogs")
    g = Graph().parse(data=r.text)
    member_uri = URIRef("https://example.com/CatalogOne")
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture()
def a_resource_link(client, a_catprez_catalog_link):
    r = client.get(a_catprez_catalog_link)
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link"))
    for link in links:
        if link != a_catprez_catalog_link:
            return link
