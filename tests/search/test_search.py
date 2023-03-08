import os
import subprocess
from time import sleep

import pytest
from rdflib import Literal, URIRef

from prez.models.search_method import SearchMethod

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def vp_test_client(request):
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
