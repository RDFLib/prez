import os
import subprocess
from time import sleep

import pytest
from fastapi.testclient import TestClient

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


def get_curie(test_client: TestClient, iri: str) -> str:
    with test_client as client:
        response = client.get(f"/identifier/curie/{iri}")
        if response.status_code != 200:
            raise ValueError(f"Failed to retrieve curie for {iri}. {response.text}")
        return response.text


@pytest.mark.parametrize(
    "iri, inbound, outbound, count",
    [
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            "http://www.w3.org/2004/02/skos/core#inScheme",
            None,
            0,
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose-no-children",
            "http://www.w3.org/2004/02/skos/core#inScheme",
            None,
            0,
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            None,
            "http://www.w3.org/2004/02/skos/core#hasTopConcept",
            0,
        ],
    ],
)
def test_count(
    test_client: TestClient,
    iri: str,
    inbound: str | None,
    outbound: str | None,
    count: int,
):
    curie = get_curie(test_client, iri)

    with test_client as client:
        params = {"curie": curie, "inbound": inbound, "outbound": outbound}
        response = client.get(f"/count", params=params)
        assert int(response.text) == count
