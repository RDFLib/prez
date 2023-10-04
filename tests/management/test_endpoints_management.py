import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from rdflib import Graph, URIRef, RDFS, RDF, DCAT

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def mgmt_test_client(request):
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


def test_annotation_predicates(mgmt_test_client):
    with mgmt_test_client as client:
        r = client.get(f"annotation-predicates")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/management/expected_responses/predicates.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )
