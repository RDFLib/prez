import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from time import sleep

import pytest
from rdflib import Graph, URIRef, RDFS, DCTERMS
from tests.local_sparql_store.store import load_vocprez_graph


PREZ_DIR = Path(__file__).parent.parent.parent.absolute() / "prez"
LOCAL_SPARQL_STORE = Path(Path(__file__).parent.parent / "local_sparql_store/store.py")
sys.path.insert(0, str(PREZ_DIR.parent.absolute()))
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
def a_vocab_id(vp_test_client):
    r = vp_test_client.get("/vocab")
    g = Graph().parse(data=r.text)
    vocab_uri = g.value(
        URIRef("https://kurrawong.net/prez/memberList"), RDFS.member, None
    )
    vocab_id = g.value(vocab_uri, DCTERMS.identifier, None)
    return vocab_id


@pytest.fixture(scope="module")
def a_vocab_id_and_a_concept_id(vp_test_client, a_vocab_id):
    # get the first concept endpoint
    # r = vp_test_client.get(f"/vocab/{a_vocab_id}")
    # g = Graph().parse(data=r.text)
    # concept_uri = g.objects(
    #     URIRef("https://kurrawong.net/prez/memberList"), RDFS.member, None
    #     )
    # vocab_id = g
    # patt = f'<a href="http://testserver/vocab/{a_vocab_id}/(.*)">'
    # TODO this works when not hard coded but the performance with *local* SPARQL store is poor
    a_vocab_id = "warox-alteration-type"
    a_concept_id = "deuteric"
    return a_vocab_id, a_concept_id


@pytest.fixture(scope="module")
def a_collection_id(vp_test_client):
    r = vp_test_client.get("/collection")
    return re.search(r'<a href="/collection/(.*)">', r.text)[1]


def test_vocab_item(vp_test_client, a_vocab_id_and_a_concept_id):
    r = vp_test_client.get(
        f"/vocab/{a_vocab_id_and_a_concept_id[0]}"
    )  # hardcoded to a smaller vocabulary - sparql store has poor performance w/ CONSTRUCT
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent / "../data/vocprez/expected_responses/vocab_html.ttl"
    )
    assert response_graph.isomorphic(expected_graph)


def test_vocab_listing(vp_test_client):
    r = vp_test_client.get(f"/vocab")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../data/vocprez/expected_responses/vocab_listing_html.ttl"
    )
    assert response_graph.isomorphic(expected_graph)


def test_concept(vp_test_client, a_vocab_id_and_a_concept_id):
    r = vp_test_client.get(
        f"/vocab/{a_vocab_id_and_a_concept_id[0]}/{a_vocab_id_and_a_concept_id[1]}"
    )
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent / "../data/vocprez/expected_responses/concept_html.ttl"
    )
    assert response_graph.isomorphic(expected_graph)


def test_collection_listing(vp_test_client):
    r = vp_test_client.get(f"/collection")
    response_graph = Graph().parse(data=r.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../data/vocprez/expected_responses/collection_listing_html.ttl"
    )
    assert response_graph.isomorphic(expected_graph)
