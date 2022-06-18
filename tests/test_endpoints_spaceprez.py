import pytest
import re
from pathlib import Path
import shutil
import os
import sys
PREZ_DIR = Path("/Users/nick/Work/Prez/prez/")
sys.path.insert(0, str(PREZ_DIR.parent.absolute()))
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def sp_test_client(request):
    print('\nDoing config setup')
    # preserve original config file
    shutil.copyfile(PREZ_DIR / "config.py", PREZ_DIR / "config.py.original")

    # alter config file contents
    with open(PREZ_DIR / "config.py", "rt") as f:
        config = f.read()
        config = config.replace("Default Prez", "Test Prez")
        config = config.replace("Default SpacePrez", "Test SpacePrez")
        config = config.replace('["VocPrez", "SpacePrez"]', '["SpacePrez"]')
        config = config.replace('"SPACEPREZ_SPARQL_ENDPOINT", ""', '"SPACEPREZ_SPARQL_ENDPOINT", "http://localhost:3030/spaceprez"')

    # write altered config contents to config.py
    with open(PREZ_DIR / "config.py", "w") as f:
        f.truncate(0)
        f.write(config)

    def teardown():
        print("\nDoing teardown")
        # remove altered config file
        os.unlink(PREZ_DIR / "config.py")

        # restore original file
        shutil.copyfile(PREZ_DIR / "config.py.original", PREZ_DIR / "config.py")
        os.unlink(PREZ_DIR / "config.py.original")

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app
    return TestClient(app)


@pytest.fixture(scope="module")
def a_dataset_link(sp_test_client):
    # get link for first dataset
    r = sp_test_client.get("/datasets?_profile=mem&_mediatype=application/json")
    return r.json()["members"][0]["link"]


@pytest.fixture(scope="module")
def a_feature_link_and_id(sp_test_client, an_fc_link):
    r3 = sp_test_client.get(f"{an_fc_link}/items?_profile=mem&_mediatype=application/json")
    feature_link = r3.json()["members"][0]["link"]
    feature_id = r3.json()["members"][0]["id"]

    return feature_link, feature_id


def test_home_default_default(sp_test_client):
    r = sp_test_client.get("/")
    assert r.status_code == 200
    assert "<h1>System Home</h1>" in r.text


def test_home_alt_html(sp_test_client):
    r = sp_test_client.get("/?_profile=alt")
    assert r.status_code == 200
    assert "<h1>Alternate Profiles</h1>" in r.text


# def test_home_alt_turtle(sp_test_client):
#     r = sp_test_client.get("/?_profile=alt&_mediatype=text/turtle")
#     assert r.status_code == 200
#     assert "<h1>Alternate Profiles</h1>" in r.text


def test_datasets_default_default(sp_test_client):
    r = sp_test_client.get("/datasets")
    assert r.status_code == 200
    assert "<h1>Dataset list</h1>" in r.text


def test_datasets_alt_html(sp_test_client):
    r = sp_test_client.get("/datasets?_profile=alt")
    assert r.status_code == 200
    assert "<h1>Alternate Profiles</h1>" in r.text


# def test_datasets_alt_turtle(sp_test_client):
#     r = sp_test_client.get("/datasets?_profile=alt&_mediatype=text/turtle")
#     assert r.status_code == 200
#     assert "<h1>Alternate Profiles</h1>" in r.text


def test_datasets_default_jsonld(sp_test_client):
    r = sp_test_client.get("/datasets?_mediatype=application/ld+json")
    assert r.status_code == 200
    assert '"@value": "A list of dcat:Datasets"' in r.text


def test_datasets_mem_json(sp_test_client):
    r = sp_test_client.get("/datasets?_profile=mem&_mediatype=application/json")
    assert r.status_code == 200
    assert '"comment":"A list of dcat:Datasets"' in r.text


def test_dataset_default_default(sp_test_client, a_dataset_link):
    r2 = sp_test_client.get(f"{a_dataset_link}")
    assert (
        f'<li class="breadcrumb"><a href="http://testserver{a_dataset_link}">'
        in r2.text
    )


def test_dataset_default_turtle(sp_test_client, a_dataset_link):
    r2 = sp_test_client.get(f"{a_dataset_link}?_mediatype=text/turtle")
    assert f"a dcat:Dataset ;" in r2.text


def test_dataset_alt_html(sp_test_client, a_dataset_link):
    r2 = sp_test_client.get(f"{a_dataset_link}?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r2.text


def test_dataset_alt_turtle(sp_test_client, a_dataset_link):
    r2 = sp_test_client.get(f"{a_dataset_link}?_profile=alt&_mediatype=text/turtle")
    assert "a rdfs:Resource ;" in r2.text


def test_dataset_collections_default_default(sp_test_client, a_dataset_link):
    r2 = sp_test_client.get(f"{a_dataset_link}/collections")
    assert f"<h1>FeatureCollection list</h1>" in r2.text


def test_dataset_collections_mem_json(sp_test_client, a_dataset_link):
    r2 = sp_test_client.get(
        f"{a_dataset_link}/collections?_profile=mem&_mediatype=application/json"
    )
    assert f'"members":' in r2.text


def test_collection_default_default(sp_test_client):
    # get link for first dataset
    r = sp_test_client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = sp_test_client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]

    r3 = sp_test_client.get(f"{col_link}")
    assert (
        '<a href="http://www.opengis.net/ont/geosparql#FeatureCollection" target="_blank" >'
        in r3.text
    )


# def test_collection_default_geojson(sp_test_client):
#     # get link for first dataset
#     r = sp_test_client.get("/datasets?_profile=mem&_mediatype=application/json")
#     link = r.json()["members"][0]["link"]
#     # get link for first collection
#     r2 = sp_test_client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
#     col_link = r2.json()["members"][0]["link"]
#
#     r3 = sp_test_client.get(f"{col_link}?_mediatype=application/geo+json")
#     assert '"type":"FeatureCollection"' in r3.text


def test_collection_alt_default(sp_test_client):
    # get link for first dataset
    r = sp_test_client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = sp_test_client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]

    r3 = sp_test_client.get(f"{col_link}?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r3.text


# def test_dataset_collection_alt_turtle():
#     # get link for first dataset
#     r = sp_test_client.get("/datasets?_profile=mem&_mediatype=application/json")
#     link = r.json()["members"][0]["link"]
#     # get link for first collection
#     r2 = sp_test_client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
#     col_link = r2.json()["members"][0]["link"]
#
#     r3 = sp_test_client.get(f"{col_link}?_profile=alt&_mediatype=text/turtle")
#     assert '<h1>Alternate Profiles</h1>' in r3.text


@pytest.fixture(scope="module")
def an_fc_link(a_dataset_link):
    # get link for first collection
    r2 = sp_test_client.get(
        f"{a_dataset_link}/collections?_profile=mem&_mediatype=application/json"
    )
    return r2.json()["members"][0]["link"]


def test_collection_items_default_default(sp_test_client, an_fc_link):
    r3 = sp_test_client.get(f"{an_fc_link}/items")
    assert "<h1>Feature list</h1>" in r3.text


def test_collection_items_mem_json(sp_test_client, an_fc_link):
    r3 = sp_test_client.get(f"{an_fc_link}/items?_profile=mem&_mediatype=application/json")
    assert (
        f'"uri":"http://testserver{an_fc_link}/items?_profile=mem&_mediatype=application/json"'
        in r3.text
    )


def test_feature_default_default(sp_test_client, a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r4 = sp_test_client.get(f"{feature_link}")
    assert f"Feature {feature_id}" in r4.text


def test_feature_default_turtle(sp_test_client, a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r4 = sp_test_client.get(f"{feature_link}?_mediatype=text/turtle")
    assert f"a geo:Feature" in r4.text


def test_feature_alt_default(sp_test_client, a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r4 = sp_test_client.get(f"{feature_link}?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r4.text
