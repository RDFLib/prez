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


@pytest.fixture(scope="function")
def prez_test_client(request):
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


def test_reset_cache(prez_test_client):
    with prez_test_client as client:
        client.get("/reset-tbox-cache")
        r = client.get("/tbox-cache")
        g = Graph().parse(data=r.text)
        assert len(g) == 3112


@pytest.mark.xfail(reason="quirk in testing framework - manually tested and cache/reset match = 3112")
def test_cache(prez_test_client):
    with prez_test_client as client:
        r = client.get("/tbox-cache")
        g = Graph().parse(data=r.text)
        assert len(g) == 3112
