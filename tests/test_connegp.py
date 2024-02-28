from pathlib import Path

import pytest
from pyoxigraph import Store
from pyoxigraph.pyoxigraph import Store
from rdflib import URIRef

from prez.app import app
from prez.dependencies import get_repo
from prez.repositories import PyoxigraphRepo, Repo
from prez.services.connegp_service import NegotiatedPMTs


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    file = Path(__file__).parent / "data/profiles/ogc_records_profile.ttl"
    store.load(file.read_bytes(), "text/turtle")

    return store


@pytest.fixture(scope="session")
def test_repo(test_store: Store) -> Repo:
    # Create a PyoxigraphQuerySender using the test_store
    return PyoxigraphRepo(test_store)


@pytest.mark.parametrize(
    "headers, params, classes, expected_selected",
    [
        [
            {},
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "text/anot+turtle",
                "class": "http://www.w3.org/ns/dcat#Catalog"
            }
        ],
    ]
)
@pytest.mark.asyncio
async def test_connegp(headers, params, classes, expected_selected, test_repo):
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    pmts = NegotiatedPMTs(headers=headers, params=params, classes=classes, system_repo=test_repo)
    success = await pmts.setup()
    assert success
    assert pmts.selected == expected_selected
