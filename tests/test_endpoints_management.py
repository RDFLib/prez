from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph

from prez.app import app
from prez.dependencies import get_repo
from prez.reference_data.prez_ns import PREZ
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


def test_annotation_predicates(client):
    r = client.get(f"/")
    response_graph = Graph().parse(data=r.text)
    labelList = list(
        response_graph.objects(
            subject=PREZ["AnnotationPropertyList"], predicate=PREZ.labelList
        )
    )
    assert len(labelList) == 1
    descriptionList = list(
        response_graph.objects(
            subject=PREZ["AnnotationPropertyList"], predicate=PREZ.descriptionList
        )
    )
    assert len(descriptionList) == 1
    provList = list(
        response_graph.objects(
            subject=PREZ["AnnotationPropertyList"], predicate=PREZ.provenanceList
        )
    )
    assert len(provList) == 1
