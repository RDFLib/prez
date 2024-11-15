import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ogctests.main import run_ogctests
from pyoxigraph.pyoxigraph import Store

from prez.app import assemble_app
from prez.dependencies import get_data_repo
from prez.repositories import PyoxigraphRepo, Repo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    file = Path(__file__).parent.parent / "test_data/ogc_features.ttl"
    store.load(file.read_bytes(), "text/turtle")

    return store


@pytest.fixture(scope="session")
def test_repo(test_store: Store) -> Repo:
    # Create a PyoxigraphQuerySender using the test_store
    return PyoxigraphRepo(test_store)


@pytest.fixture(scope="session")
def client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_data_repo():
        return test_repo

    app = assemble_app()

    app.dependency_overrides[get_data_repo] = override_get_data_repo

    with TestClient(app, backend_options={"loop_factory": asyncio.new_event_loop}) as c:
        c.base_url = "http://localhost:8000/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features"
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "test_file",
    [
        pytest.param(
            "apidefinition",
            marks=pytest.mark.xfail(
                reason="see https://github.com/RDFLib/prez/pull/265#issuecomment-2367130294"
            ),
        ),
        "collection",
        "collections",
        "conformance",
        pytest.param(
            "crs",
            marks=pytest.mark.xfail(
                reason="see https://github.com/RDFLib/prez/issues/267"
            ),
        ),
        "errorconditions",
        "feature",
                pytest.param(
            "features",
            marks=pytest.mark.xfail(
                reason="endpoint that causes an error in pytest works manually with the same data in Fuseki"
            ),
        ),
        "general",
        "landingpage",
    ],
)
def test_features_core(client: TestClient, test_file: str):
    scope = f"features/core/test_{test_file}.py"
    exit_code = run_ogctests(scope, test_client=client)
    assert exit_code == pytest.ExitCode.OK
