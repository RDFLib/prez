import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from rdflib import Literal, URIRef, Graph
from rdflib.compare import isomorphic

from prez.models.search_method import SearchMethod

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


def test_search_preflabel(test_client: TestClient):
    with test_client as client:
        response = client.get(
            f"/search?term=Coal&method=skosPrefLabel&filter[skos:inScheme]=2016.01:contacttype"
        )
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/vocprez/expected_responses/collection_listing_anot.ttl"
        )
        assert isomorphic(expected_graph, response_graph)
