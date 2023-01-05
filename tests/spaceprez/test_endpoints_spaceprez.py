import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from rdflib import Graph, URIRef, RDFS

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")
from fastapi.testclient import TestClient

# https://www.python-httpx.org/advanced/#calling-into-python-web-apps


@pytest.fixture(scope="module")
def sp_test_client(request):
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
def a_dataset_link(sp_test_client):
    with sp_test_client as client:
        # get link for first dataset
        r = client.get("/s/datasets")
        g = Graph().parse(data=r.text)
        member_uri = g.value(URIRef("https://prez.dev/DatasetList"), RDFS.member, None)
        link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
        return link


@pytest.fixture(scope="module")
def an_fc_link(sp_test_client, a_dataset_link):
    with sp_test_client as client:
        # get link for a dataset's collections
        r = client.get(f"{a_dataset_link}/collections")
    g = Graph().parse(data=r.text)
    member_uri = g.value(
        URIRef("http://example.com/datasets/sandgate"), RDFS.member, None
    )
    link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return link


@pytest.fixture(scope="module")
def a_feature_link(sp_test_client, an_fc_link):
    with sp_test_client as client:
        r = client.get(f"{an_fc_link}/items")
        g = Graph().parse(data=r.text)
        member_uri = g.value(
            URIRef("http://example.com/datasets/sandgate/catchments"), RDFS.member, None
        )
        link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
        return link


@pytest.fixture(scope="module")
def a_dataset_uri(sp_test_client):
    # get uri for first dataset
    with sp_test_client as client:
        r = client.get("/datasets")
        g = Graph().parse(data=r.text)
        member_uri = g.value(URIRef("https://prez.dev/memberList"), RDFS.member, None)
        return member_uri


def test_dataset_anot(sp_test_client, a_dataset_link):
    with sp_test_client as client:
        r = client.get(f"{a_dataset_link}?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/dataset_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_collection_anot(sp_test_client, an_fc_link):
    with sp_test_client as client:
        r = client.get(f"{an_fc_link}?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_collection_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_anot(sp_test_client, a_feature_link):
    with sp_test_client as client:
        r = client.get(f"{a_feature_link}?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_dataset_listing_anot(sp_test_client):
    with sp_test_client as client:
        r = client.get("/s/datasets?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/dataset_listing_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_collection_listing_anot(sp_test_client, a_dataset_link):
    with sp_test_client as client:
        r = client.get(f"{a_dataset_link}/collections?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_collection_listing_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_listing_anot(sp_test_client, an_fc_link):
    with sp_test_client as client:
        r = client.get(f"{an_fc_link}/items?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_listing_anot.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )
