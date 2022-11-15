import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from time import sleep

from rdflib import Graph, URIRef, RDFS, DCTERMS, SKOS

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")
from fastapi.testclient import TestClient

# https://www.python-httpx.org/advanced/#calling-into-python-web-apps


@pytest.fixture(scope="module")
def sp_test_client(request):
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
def a_catalog_link(sp_test_client):
    with sp_test_client as client:
        # get link for first catalog
        r = client.get("/c/catalogs")
        g = Graph().parse(data=r.text)
        member_uri = g.value(
            URIRef("https://kurrawong.net/prez/memberList"), RDFS.member, None
        )
        link = g.value(member_uri, URIRef(f"https://kurrawong.net/prez/link", None))
        return link


@pytest.fixture(scope="module")
def a_resource_link(sp_test_client, a_catalog_link):
    with sp_test_client as client:
        # get link for a dataset's collections
        r = client.get(f"{a_catalog_link}/collections")
        g = Graph().parse(data=r.text)
        member_uri = g.value(
            URIRef("https://kurrawong.net/prez/memberList"), RDFS.member, None
        )
        link = g.value(member_uri, URIRef(f"https://kurrawong.net/prez/link", None))
        return link


@pytest.fixture(scope="module")
def a_feature_link_and_id(sp_test_client, an_fc_link):
    with sp_test_client as client:
        r = client.get(f"{an_fc_link}/items")
        g = Graph().parse(data=r.text)
        member_uri = g.value(
            URIRef("https://kurrawong.net/prez/memberList"), RDFS.member, None
        )
        link = g.value(member_uri, URIRef(f"https://kurrawong.net/prez/link", None))
        id = g.value(member_uri, DCTERMS.identifier, None)
        return link, id


@pytest.fixture(scope="module")
def a_dataset_uri(sp_test_client):
    # get uri for first dataset
    with sp_test_client as client:
        r = client.get("/datasets")
        g = Graph().parse(data=r.text)
        member_uri = g.value(
            URIRef("https://kurrawong.net/prez/memberList"), RDFS.member, None
        )
        return member_uri


def test_dataset_html(sp_test_client, a_catalog_link):
    with sp_test_client as client:
        r = client.get(f"{a_catalog_link}")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/dataset_html.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_collection_html(sp_test_client, an_fc_link):
    with sp_test_client as client:
        r = client.get(f"{an_fc_link}")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_collection_html.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_html(sp_test_client, a_feature_link_and_id):
    with sp_test_client as client:
        r = client.get(f"{a_feature_link_and_id[0]}")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_html.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_dataset_listing_html(sp_test_client):
    with sp_test_client as client:
        r = client.get(f"/s/datasets")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/dataset_listing_html.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_collection_listing_html(sp_test_client, a_dataset_link):
    with sp_test_client as client:
        r = client.get(f"{a_dataset_link}/collections")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_collection_listing_html.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


def test_feature_listing_html(sp_test_client, an_fc_link):
    with sp_test_client as client:
        r = client.get(f"{an_fc_link}/items")
        response_graph = Graph().parse(data=r.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/spaceprez/expected_responses/feature_listing_html.ttl"
        )
        assert response_graph.isomorphic(expected_graph), print(
            f"Graph delta:{(expected_graph - response_graph).serialize()}"
        )


# def test_object_endpoint_dataset(sp_test_client, a_dataset_uri):
#     r = sp_test_client.get(f"/object?uri={a_dataset_uri}")
#     assert f'<a href="{a_dataset_uri}"' in r.text
#
#
# def test_object_endpoint_feature_collection(sp_test_client, an_fc_uri):
#     r = sp_test_client.get(f"/object?uri={an_fc_uri}")
#     assert f'<a href="{an_fc_uri}"' in r.text
#
#
# def test_object_endpoint_feature(sp_test_client, a_feature_uri):
#     r = sp_test_client.get(f"/object?uri={a_feature_uri}")
#     assert f'<a href="{a_feature_uri}"' in r.text
