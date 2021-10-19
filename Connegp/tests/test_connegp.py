import pytest
from connegp import Connegp, Profile, RDF_MEDIATYPES

from .request_objects import (
    FastAPIRequest,
    FlaskRequest,
    InvalidHeadersRequest,
    InvalidQSARequest,
)

dcat = Profile(
    uri="https://www.w3.org/TR/vocab-dcat/",
    id="dcat",
    label="DCAT",
    comment="Dataset Catalogue Vocabulary (DCAT) is a W3C-authored RDF vocabulary designed to "
    "facilitate interoperability between data catalogs "
    "published on the Web.",
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/html",
    languages=["en"],
    default_language="en",
)

skos = Profile(
    uri="https://www.w3.org/TR/skos-reference/",
    id="skos",
    label="SKOS",
    comment="Simple Knowledge Organization System (SKOS) is a W3C-authored, common data model for sharing "
    "and linking knowledge organization systems "
    "via the Web.",
    mediatypes=RDF_MEDIATYPES,
    default_mediatype="text/turtle",
    languages=["en"],
    default_language="en",
)


def test_base_fastapi():
    """Tests that the default profile token is return if nothing is provided"""
    headers = {}
    query_params = {}

    request = FastAPIRequest(headers, query_params)

    c = Connegp(request, {"skos": skos, "dcat": dcat}, "dcat")

    assert c.profile == "dcat"


def test_base_flask():
    """Tests that the default profile token is return if nothing is provided"""
    headers = {}
    args = {}

    request = FlaskRequest(headers, args)

    c = Connegp(request, {"skos": skos, "dcat": dcat}, "dcat")

    assert c.profile == "dcat"


def test_get_profile_qsa_fastapi():
    """Tests that the correct profile is returned from QSA"""
    headers = {}
    query_params = {"_profile": "skos", "_mediatype": "text/turtle"}

    request = FastAPIRequest(headers, query_params)

    c = Connegp(request, {"skos": skos, "dcat": dcat}, "dcat")

    assert c.profile == "skos"


def test_get_profile_qsa_flask():
    """Tests that the correct profile is returned from QSA"""
    headers = {}
    args = {"_profile": "skos", "_mediatype": "text/turtle"}

    request = FlaskRequest(headers, args)

    c = Connegp(request, {"skos": skos, "dcat": dcat}, "dcat")

    assert c.profile == "skos"


def test_get_profile_accept_header_fastapi():
    """Tests that the correct profile is returned from an Accept-Profile header"""
    headers = {
        "Accept-Profile": "<https://www.w3.org/TR/skos-reference/>;q=1.0,<https://www.w3.org/TR/vocab-dcat/>;q=0.8"
    }
    query_params = {}

    request = FastAPIRequest(headers, query_params)

    c = Connegp(request, {"skos": skos, "dcat": dcat}, "dcat")

    assert c.profile == "skos"


def test_get_profile_accept_header_flask():
    """Tests that the correct profile is returned from an Accept-Profile header"""
    headers = {
        "Accept-Profile": "<https://www.w3.org/TR/skos-reference/>;q=1.0,<https://www.w3.org/TR/vocab-dcat/>;q=0.8"
    }
    args = {}

    request = FlaskRequest(headers, args)

    c = Connegp(request, {"skos": skos, "dcat": dcat}, "dcat")

    assert c.profile == "skos"


def test_unsupported_request_qsa_fastapi():
    """
    Tests that an invalid Request object (from an unsupported web framework)
    correctly throws an error
    """
    headers = {}
    params = {"_profile": "skos", "_mediatype": "text/turtle"}

    request = InvalidQSARequest(headers, params)

    with pytest.raises(AttributeError):
        c = Connegp(request, {"skos": skos, "dcat": dcat}, "dcat")
