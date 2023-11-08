import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from rdflib import Graph

from prez.reference_data.prez_ns import PREZ

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
        r = client.get(f"/")
        response_graph = Graph().parse(data=r.text)
        labelList = list(
            response_graph.objects(
                subject=PREZ["AnnotationPropertyList"], predicate=PREZ.labelList
            )
        )
        assert len(labelList) == 1
        descriptionList = list(
            response_graph.objects(
                subject=PREZ["AnnotationPropertyList"], predicate=PREZ.descriptionList
            )
        )
        assert len(descriptionList) == 1
        provList = list(
            response_graph.objects(
                subject=PREZ["AnnotationPropertyList"], predicate=PREZ.provenanceList
            )
        )
        assert len(provList) == 1
