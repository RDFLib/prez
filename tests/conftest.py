import os

from rdflib import Graph, URIRef
from starlette.routing import Mount

# comment / uncomment for the CQL tests - cannot figure out how to get a different conftest picked up.
os.environ["SPARQL_REPO_TYPE"] = "pyoxigraph_memory"

# os.environ["SPARQL_ENDPOINT"] = "http://localhost:3030/dataset"
# os.environ["SPARQL_REPO_TYPE"] = "remote"
os.environ["ENABLE_SPARQL_ENDPOINT"] = "true"

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store, RdfFormat

from prez.app import assemble_app
from prez.config import Settings
from prez.dependencies import get_data_repo
from prez.repositories import PyoxigraphRepo, Repo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in (Path(__file__).parent.parent / "test_data").glob("**/*.ttl"):
        store.load(file.read_bytes(), RdfFormat.TURTLE)

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

    app = assemble_app(
        local_settings=Settings(
            _env_file=None,
            sparql_repo_type="pyoxigraph_memory",
            enable_sparql_endpoint=True,
        )
    )

    app.dependency_overrides[get_data_repo] = override_get_repo

    for route in app.routes:
        if isinstance(route, Mount):
            route.app.dependency_overrides[get_data_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client_no_override() -> TestClient:
    app = assemble_app(
        local_settings=Settings(
            _env_file=None,
            sparql_repo_type="pyoxigraph_memory",
            enable_sparql_endpoint=True,
        )
    )

    with TestClient(app) as c:
        yield c


def link_for(client, listing_path: str, uri: str):
    """The prez:link for one object in a listing, whatever page it would fall on.

    The listings have no ORDER BY, so which items land on the default first page is
    whatever order the store returns them in, and that varies by platform. Asking
    for the whole listing keeps these fixtures from depending on it.
    """
    response = client.get(listing_path, params={"limit": 1000})
    graph = Graph().parse(data=response.text)
    link = graph.value(URIRef(uri), URIRef("https://prez.dev/link"))
    assert link is not None, f"no prez:link for {uri} in {listing_path}"
    return link


@pytest.fixture()
def a_spaceprez_catalog_link(client):
    return link_for(
        client, "/catalogs", "https://example.com/spaceprez/SpacePrezCatalog"
    )


@pytest.fixture()
def a_spaceprez_dataset_link(client, a_spaceprez_catalog_link):
    return link_for(
        client,
        f"{a_spaceprez_catalog_link}/collections",
        "https://example.com/spaceprez/SpacePrezDataset",
    )


@pytest.fixture()
def an_fc_link(client, a_spaceprez_dataset_link):
    return (
        f"{a_spaceprez_dataset_link}/features/collections/spaceprez:FeatureCollection"
    )


@pytest.fixture()
def a_feature_link(client, an_fc_link):
    return f"{an_fc_link}/items/spaceprez:Feature1"


@pytest.fixture()
def a_catprez_catalog_link(client):
    return link_for(client, "/catalogs", "https://example.com/CatalogOne")


@pytest.fixture()
def a_resource_link(client, a_catprez_catalog_link):
    r = client.get(a_catprez_catalog_link)
    g = Graph().parse(data=r.text)
    links = g.objects(subject=None, predicate=URIRef("https://prez.dev/link"))
    for link in links:
        if link != a_catprez_catalog_link:
            return link
