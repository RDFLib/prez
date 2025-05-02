import pytest
from rdflib import URIRef

from prez.reference_data.prez_ns import PREZ
from prez.repositories import PyoxigraphRepo
from prez.services.connegp_service import NegotiatedPMTs


@pytest.mark.parametrize(
    "headers, params, classes, listing, expected_selected",
    [
        # [
        #     {},  # Test that profiles/mediatypes resolve to their defaults if not requested (object endpoint)
        #     {},
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     False,
        #     {
        #         "profile": URIRef("https://prez.dev/OGCItemProfile"),
        #         "title": "OGC Object Profile",
        #         "mediatype": "text/anot+turtle",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
        # [
        #     {},  # Test that profiles/mediatypes resolve to their defaults if not requested (listing endpoint)
        #     {},
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     True,
        #     {
        #         "profile": URIRef("https://prez.dev/OGCListingProfile"),
        #         "title": "OGC Listing Profile",
        #         "mediatype": "text/anot+turtle",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
        # [
        #     {
        #         "accept": "application/ld+json"
        #     },  # Test that a valid mediatype is resolved
        #     {},
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     False,
        #     {
        #         "profile": URIRef("https://prez.dev/OGCItemProfile"),
        #         "title": "OGC Object Profile",
        #         "mediatype": "application/ld+json",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
        # [
        #     {
        #         "accept": "application/ld+json;q=0.7,text/turtle"
        #     },  # Test resolution of multiple mediatypes
        #     {},
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     False,
        #     {
        #         "profile": URIRef("https://prez.dev/OGCItemProfile"),
        #         "title": "OGC Object Profile",
        #         "mediatype": "text/turtle",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
        # [
        #     {},
        #     {"_mediatype": "application/ld+json"},  # Test mediatype resolution as QSA
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     False,
        #     {
        #         "profile": URIRef("https://prez.dev/OGCItemProfile"),
        #         "title": "OGC Object Profile",
        #         "mediatype": "application/ld+json",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
        # [
        #     {"accept": "text/turtle"},
        #     {"_mediatype": "application/ld+json"},  # Test QSA mediatype is preferred
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     False,
        #     {
        #         "profile": URIRef("https://prez.dev/OGCItemProfile"),
        #         "title": "OGC Object Profile",
        #         "mediatype": "application/ld+json",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
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
        # [
        #     {"accept": "oogabooga"},  # Test that invalid mediatype is ignored
        #     {},
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     False,
        #     {
        #         "profile": URIRef("https://prez.dev/OGCItemProfile"),
        #         "title": "OGC Object Profile",
        #         "mediatype": "text/anot+turtle",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
        # [
        #     {
        #         "accept-profile": "http://www.w3.org/ns/dx/prof/Profile"
        #     },  # Test that a valid profile is resolved
        #     {},
        #     [URIRef("http://www.w3.org/ns/dcat#Catalog")],
        #     True,
        #     {
        #         "profile": PREZ["OGCListingProfile"],
        #         "title": "OGC Listing Profile",
        #         "mediatype": "text/anot+turtle",
        #         "class": "http://www.w3.org/ns/dcat#Catalog",
        #     },
        # ],
    ],
)
@pytest.mark.asyncio
async def test_connegp(
    headers, params, classes, listing, expected_selected, client_no_override
):
    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    system_repo = PyoxigraphRepo(system_store)
    pmts = NegotiatedPMTs(
        headers=headers,
        params=params,
        classes=classes,
        listing=listing,
        system_repo=system_repo,
    )
    await pmts.setup()
    assert pmts.selected == expected_selected
