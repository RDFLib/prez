import pytest
from rdflib import URIRef

from prez.services.curie_functions import get_curie_id_for_uri, get_uri_for_curie_id


def test_id_generation_fragment_uri():
    assert (
            get_curie_id_for_uri(
                uri="http://www.w3.org/2004/02/skos/core#prefLabel",
                separator="-",
            )
            == "skos-prefLabel"
    )


def test_id_generation_no_fragment_uri():
    assert (
            get_curie_id_for_uri(
                uri="http://www.w3.org/ns/dx/prof/Profile",
                separator="-",
            )
            == "prof-Profile"
    )

def test_negative_namespace_fragment():
    assert pytest.raises(ValueError, get_curie_id_for_uri, "http://www.w3.org/ns/dx/conneg/altr-ext#", "-")


def test_negative_namespace_no_fragment():
    assert pytest.raises(ValueError, get_curie_id_for_uri, "http://www.w3.org/ns/dx/conneg/altr-ext/", "-")


def test_get_uri_for_curie_id():
    assert (
            get_uri_for_curie_id(
                curie_id="skos-prefLabel",
                separator="-",
            )
            == URIRef("http://www.w3.org/2004/02/skos/core#prefLabel")
    )