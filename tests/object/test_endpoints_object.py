import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from rdflib import Graph, URIRef, RDFS, RDF, DCAT

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")
from fastapi.testclient import TestClient

# https://www.python-httpx.org/advanced/#calling-into-python-web-apps


@pytest.fixture(scope="module")
def test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3032"])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app

    return TestClient(app)


@pytest.fixture(scope="module")
def dataset_uri(test_client):
    with test_client as client:
        # get link for first dataset
        r = client.get("/s/datasets")
    g = Graph().parse(data=r.text)
    return g.value(None, RDF.type, DCAT.Dataset)


def test_object_endpoint_sp_dataset(test_client, dataset_uri):
    with test_client as client:
        r = client.get(f"/object?uri={dataset_uri}")
    assert r.status_code == 200


def test_feature_collection(test_client):
    with test_client as client:
        r = client.get(f"/object?uri=https://test/feature-collection")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent / "../data/object/expected_responses/fc.ttl"
    )
    assert response_graph.isomorphic(expected_graph)


def test_feature(test_client):
    with test_client as client:
        r = client.get(
            f"/object?uri=https://linked.data.gov.au/datasets/geofabric/hydroid/102208962"
        )
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent / "../data/object/expected_responses/feature.ttl"
    )
    assert response_graph.isomorphic(expected_graph)
