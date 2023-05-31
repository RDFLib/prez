import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from rdflib import Graph, URIRef, RDF, DCAT

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")
from fastapi.testclient import TestClient

# https://www.python-httpx.org/advanced/#calling-into-python-web-apps


@pytest.fixture(scope="module")
def cp_test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3033"])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app

    return TestClient(app)


@pytest.fixture(scope="module")
def a_catalog_link(cp_test_client):
    with cp_test_client as client:
        # get link for first catalog
        r = client.get("/c/catalogs")
        g = Graph().parse(data=r.text)
        member_uri = g.value(None, RDF.type, DCAT.Catalog)
        link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
        return link


@pytest.fixture(scope="module")
def a_resource_link(cp_test_client, a_catalog_link):
    with cp_test_client as client:
        r = client.get(a_catalog_link)
        g = Graph().parse(data=r.text)
        link = next(g.objects(subject=None, predicate=URIRef(f"https://prez.dev/link")))
        return link


def test_catalog_anot(cp_test_client, a_catalog_link):
    with cp_test_client as client:
        r = client.get(f"{a_catalog_link}?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/catprez/expected_responses/catalog_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_resource_anot(cp_test_client, a_resource_link):
    with cp_test_client as client:
        r = client.get(f"{a_resource_link}?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/catprez/expected_responses/resource_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )
