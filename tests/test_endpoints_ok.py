import logging
import time
from pathlib import Path
from typing import Optional, Set

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph

from prez.app import app
from prez.dependencies import get_repo
from prez.reference_data.prez_ns import PREZ
from prez.repositories import Repo, PyoxigraphRepo

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../test_data/*.ttl"):
        store.load(file.read_bytes(), "text/turtle")

    return store


def wait_for_app_to_be_ready(client, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = client.get("/health")
            if response.status_code == 200:
                return
        except Exception as e:
            print(e)
        time.sleep(0.5)
    raise RuntimeError("App did not start within the specified timeout")


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
        wait_for_app_to_be_ready(c)
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


def test_ogcprez_links(
    client: TestClient, visited: Optional[Set] = None, link="/catalogs"
):
    if not visited:
        visited = set()
    response = client.get(link)
    g = Graph().parse(data=response.text, format="turtle")
    links = list(g.objects(None, PREZ.link))
    member_bnode_list = list(g.objects(None, PREZ.members))
    if member_bnode_list:
        member_bnode = member_bnode_list[0]
        member_links = list(g.objects(member_bnode, PREZ.link))
        links.extend(member_links)
    assert response.status_code == 200
    for link in links:
        print(link)
        if link not in visited:
            visited.add(link)
            test_ogcprez_links(client, visited, str(link))
