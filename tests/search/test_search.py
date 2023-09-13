import os
import subprocess
from pathlib import Path
from time import sleep
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from rdflib import Literal, URIRef, Graph
from rdflib.compare import isomorphic

from prez.models.search_method import SearchMethod
from prez.routers.search import extract_qsa_params

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")


@pytest.fixture(scope="module")
def test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3031"])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app

    return TestClient(app)


@pytest.fixture(scope="module")
def test_method_creation():
    method = SearchMethod(
        uri=URIRef("https://prez.dev/uri"),
        identifier=Literal("identifier"),
        title=Literal("title"),
        query=Literal("query"),
    )
    return method


def test_search_focus_to_filter(test_client: TestClient):
    base_url = "/search"
    params = {
        "term": "contact",
        "method": "default",
        "focus-to-filter[skos:broader]": "http://resource.geosciml.org/classifier/cgi/contacttype/metamorphic_contact",
    }
    # Constructing the final URL
    final_url = f"{base_url}?{urlencode(params)}"
    with test_client as client:
        response = client.get(final_url)
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/search/expected_responses/focus_to_filter_search.ttl"
        )
        assert isomorphic(expected_graph, response_graph)


def test_search_filter_to_focus(test_client: TestClient):
    base_url = "/search"
    params = {
        "term": "storage",
        "method": "default",
        "filter-to-focus[skos:broader]": "http://linked.data.gov.au/def/borehole-purpose/carbon-capture-and-storage",
    }
    # Constructing the final URL
    final_url = f"{base_url}?{urlencode(params)}"
    with test_client as client:
        response = client.get(final_url)
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/search/expected_responses/filter_to_focus_search.ttl"
        )
        assert isomorphic(expected_graph, response_graph)


@pytest.mark.xfail(
    reason="This generates a valid query that has been tested in Fuseki, which RDFLib struggles with"
)
def test_search_filter_to_focus_multiple(test_client: TestClient):
    base_url = "/search"
    params = {
        "term": "storage",
        "method": "default",
        "filter-to-focus[skos:broader]": "http://resource.geosciml.org/classifier/cgi/contacttype/metamorphic_contact,http://linked.data.gov.au/def/borehole-purpose/greenhouse-gas-storage",
    }
    # Constructing the final URL
    final_url = f"{base_url}?{urlencode(params)}"
    with test_client as client:
        response = client.get(final_url)
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/search/expected_responses/filter_to_focus_search.ttl"
        )
        assert isomorphic(expected_graph, response_graph)


@pytest.mark.xfail(
    reason="This generates a valid query that has been tested in Fuseki, which RDFLib struggles with"
)
def test_search_focus_to_filter_multiple(test_client: TestClient):
    base_url = "/search"
    params = {
        "term": "storage",
        "method": "default",
        "focus-to-filter[skos:broader]": "http://linked.data.gov.au/def/borehole-purpose/carbon-capture-and-storage,http://linked.data.gov.au/def/borehole-purpose/pggd",
    }
    # Constructing the final URL
    final_url = f"{base_url}?{urlencode(params)}"
    with test_client as client:
        response = client.get(final_url)
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/search/expected_responses/filter_to_focus_search.ttl"
        )
        assert isomorphic(expected_graph, response_graph)


@pytest.mark.parametrize(
    "qsas, expected_focus_to_filter, expected_filter_to_focus",
    [
        (
            {
                "term": "value1",
                "method": "value2",
                "filter-to-focus[rdfs:member]": "value3",
                "focus-to-filter[dcterms:title]": "value4",
            },
            [(URIRef("http://purl.org/dc/terms/title"), "value4")],
            [(URIRef("http://www.w3.org/2000/01/rdf-schema#member"), "value3")],
        ),
        (
            {
                "term": "value1",
                "method": "value2",
                "focus-to-filter[dcterms:title]": "value4",
            },
            [(URIRef("http://purl.org/dc/terms/title"), "value4")],
            [],
        ),
        (
            {
                "term": "value1",
                "method": "value2",
                "filter-to-focus[rdfs:member]": "value3",
            },
            [],
            [(URIRef("http://www.w3.org/2000/01/rdf-schema#member"), "value3")],
        ),
        ({"term": "value1", "method": "value2"}, [], []),
    ],
)
def test_extract_qsa_params(qsas, expected_focus_to_filter, expected_filter_to_focus):
    focus_to_filter_params, filter_to_focus_params = extract_qsa_params(qsas)

    assert focus_to_filter_params == expected_focus_to_filter
    assert filter_to_focus_params == expected_filter_to_focus
