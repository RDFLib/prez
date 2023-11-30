from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, PROF

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
def client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


def test_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/profile/prez"), RDF.type, PROF.Profile) in g


def test_cp_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles/prez:CatPrezProfile")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/CatPrezProfile"), RDF.type, PROF.Profile) in g


def test_sp_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles/prez:SpacePrezProfile")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/SpacePrezProfile"), RDF.type, PROF.Profile) in g


def test_vp_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles/prez:VocPrezProfile")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/VocPrezProfile"), RDF.type, PROF.Profile) in g


def test_pp_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles/prez:profiles")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/profiles"), RDF.type, PROF.Profile) in g
