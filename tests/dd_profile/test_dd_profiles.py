import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph
from rdflib.compare import isomorphic

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


# def test_vocab_listing(test_client: TestClient):
#     with test_client as client:
#         response = client.get(f"/v/vocab?_mediatype=text/anot+turtle")
#         response_graph = Graph().parse(data=response.text)
#         expected_graph = Graph().parse(
#             Path(__file__).parent
#             / "../data/vocprez/expected_responses/vocab_listing_anot.ttl"
#         )
