import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from rdflib import Literal, URIRef, Graph
from rdflib.compare import isomorphic

from prez.models.search_method import SearchMethod
from prez.routers.search import extract_qsa_params

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")
from fastapi.testclient import TestClient


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


def test_serialisation(test_method_creation):
    with test_method_creation as method:
        g = method.serialize()


def test_search_focus_to_filter(test_client: TestClient):
    with test_client as client:
        response = client.get(
            f"/search?term=contact&method=default&focus-to-filter[skos:broader]=http://resource.geosciml.org/classifier/cgi/contacttype/metamorphic_contact"
        )
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/vocprez/expected_responses/collection_listing_anot.ttl"
        )
        assert isomorphic(expected_graph, response_graph)


def test_search_filter_to_focus(test_client: TestClient):
    with test_client as client:
        response = client.get(
            f"/search?term=exactMatch&method=exactMatch&filter-to-focus[rdfs:member]=2016.01:contacttype"
        )
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/vocprez/expected_responses/collection_listing_anot.ttl"
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
