import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store

from prez.app import app
from prez.dependencies import get_repo
from prez.repositories import PyoxigraphRepo, Repo

from ogctests.main import run_ogctests


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    file = Path("../test_data/spaceprez.ttl")
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

    with TestClient(app, backend_options={'loop_factory': asyncio.new_event_loop}) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


def test_features_core(client: TestClient):
    scope = "features/core"
    run_ogctests(scope, client)
