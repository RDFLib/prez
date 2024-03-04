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
    store = Store()
    file = Path(__file__).parent / "data/profiles/ogc_records_profile.ttl"
    store.load(file.read_bytes(), "text/turtle")
    file = Path(__file__).parent / "data/profiles/spaceprez_default_profiles.ttl"
    store.load(file.read_bytes(), "text/turtle")
    return store


@pytest.fixture(scope="session")
def test_repo(test_store: Store) -> Repo:
    return PyoxigraphRepo(test_store)


@pytest.mark.parametrize(
    "headers, params, classes, listing, expected_selected",
    [
        [
            {},  # Test that profiles/mediatypes resolve to their defaults if not requested (object endpoint)
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            False,
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "text/anot+turtle",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {},  # Test that profiles/mediatypes resolve to their defaults if not requested (listing endpoint)
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            True,
            {
                "profile": URIRef("https://prez.dev/OGCListingProfile"),
                "title": "OGC Listing Profile",
                "mediatype": "text/anot+turtle",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {
                "accept": "application/ld+json"
            },  # Test that a valid mediatype is resolved
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            False,
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "application/ld+json",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {
                "accept": "application/ld+json;q=0.7,text/turtle"
            },  # Test resolution of multiple mediatypes
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            False,
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "text/turtle",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {},
            {"_media": "application/ld+json"},  # Test mediatype resolution as QSA
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            False,
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "application/ld+json",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {"accept": "text/turtle"},
            {"_media": "application/ld+json"},  # Test QSA mediatype is preferred
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            False,
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "application/ld+json",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {"accept-profile": "oogabooga"},  # Test that invalid profile is ignored
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            False,
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "text/anot+turtle",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {"accept": "oogabooga"},  # Test that invalid mediatype is ignored
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            False,
            {
                "profile": URIRef("https://prez.dev/OGCItemProfile"),
                "title": "OGC Object Profile",
                "mediatype": "text/anot+turtle",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
        [
            {
                "accept-profile": "<http://www.w3.org/ns/dx/prof/Profile>"
            },  # Test that a valid profile is resolved
            {},
            [URIRef("http://www.w3.org/ns/dcat#Catalog")],
            True,
            {
                "profile": URIRef("https://www.w3.org/TR/vocab-dcat/"),
                "title": "DCAT",
                "mediatype": "text/anot+turtle",
                "class": "http://www.w3.org/ns/dcat#Catalog",
            },
        ],
    ],
)
@pytest.mark.asyncio
async def test_connegp(headers, params, classes, listing, expected_selected, test_repo):
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo
    pmts = NegotiatedPMTs(
        headers=headers,
        params=params,
        classes=classes,
        listing=listing,
        system_repo=test_repo,
    )
    success = await pmts.setup()
    assert success
    assert pmts.selected == expected_selected
