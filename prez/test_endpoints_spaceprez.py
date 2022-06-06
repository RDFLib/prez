from fastapi.testclient import TestClient
import pytest

from app import app
from config import *


client = TestClient(app)


def test_home_default_default():
    if len(ENABLED_PREZS) == 1 and ENABLED_PREZS[0].lower() == "spaceprez":
        r = client.get("/")
        assert r.status_code == 200
        assert "<h1>System Home</h1>" in r.text
    elif "spaceprez" in [prez.lower() for prez in ENABLED_PREZS]:
        r = client.get("/spaceprez")
        assert r.status_code == 200
        assert "<h1>SpacePrez Home</h1>" in r.text
    else:
        assert True


def test_home_alt_html():
    if len(ENABLED_PREZS) == 1 and ENABLED_PREZS[0].lower() == "spaceprez":
        r = client.get("/?_profile=alt")
    elif "spaceprez" in [prez.lower() for prez in ENABLED_PREZS]:
        r = client.get("/spaceprez?_profile=alt")
    else:
        assert True
    assert r.status_code == 200
    assert "<h1>Alternate Profiles</h1>" in r.text


# def test_home_alt_turtle():
#     r = client.get("/?_profile=alt&_mediatype=text/turtle")
#     assert r.status_code == 200
#     assert "<h1>Alternate Profiles</h1>" in r.text


def test_datasets_default_default():
    r = client.get("/datasets")
    assert r.status_code == 200
    assert "<h1>Dataset list</h1>" in r.text


def test_datasets_alt_html():
    r = client.get("/datasets?_profile=alt")
    assert r.status_code == 200
    assert "<h1>Alternate Profiles</h1>" in r.text


# def test_datasets_alt_turtle():
#     r = client.get("/datasets?_profile=alt&_mediatype=text/turtle")
#     assert r.status_code == 200
#     assert "<h1>Alternate Profiles</h1>" in r.text


def test_datasets_default_jsonld():
    r = client.get("/datasets?_mediatype=application/ld+json")
    assert r.status_code == 200
    assert '"@value": "A list of dcat:Datasets"' in r.text


def test_datasets_mem_json():
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    assert r.status_code == 200
    assert '"comment":"A list of dcat:Datasets"' in r.text


@pytest.fixture(scope="module")
def a_dataset_link():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    return r.json()["members"][0]["link"]


def test_dataset_default_default(a_dataset_link):
    r2 = client.get(f"{a_dataset_link}")
    assert f'<li class="breadcrumb"><a href="http://testserver{a_dataset_link}">' in r2.text


def test_dataset_default_turtle(a_dataset_link):
    r2 = client.get(f"{a_dataset_link}?_mediatype=text/turtle")
    assert f'a dcat:Dataset ;' in r2.text # prefix could be e.g. ns18: instead of dcat:


def test_dataset_alt_html(a_dataset_link):
    r2 = client.get(f"{a_dataset_link}?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r2.text


def test_dataset_alt_turtle(a_dataset_link):
    r2 = client.get(f"{a_dataset_link}?_profile=alt&_mediatype=text/turtle")
    assert "a rdfs:Resource ;" in r2.text


def test_dataset_collections_default_default(a_dataset_link):
    r2 = client.get(f"{a_dataset_link}/collections")
    assert f'<h1>FeatureCollection list</h1>' in r2.text


def test_dataset_collections_mem_json(a_dataset_link):
    r2 = client.get(f"{a_dataset_link}/collections?_profile=mem&_mediatype=application/json")
    assert f'"members":' in r2.text


def test_collection_default_default():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]

    r3 = client.get(f"{col_link}")
    assert '<a href="http://www.opengis.net/ont/geosparql#FeatureCollection" target="_blank" >' in r3.text


def test_collection_default_geojson():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]

    r3 = client.get(f"{col_link}?_mediatype=application/vnd.geo+json")
    assert '"type":"FeatureCollection"' in r3.text


def test_collection_alt_default():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]

    r3 = client.get(f"{col_link}?_profile=alt")
    assert '<h1>Alternate Profiles</h1>' in r3.text


# def test_dataset_collection_alt_turtle():
#     # get link for first dataset
#     r = client.get("/datasets?_profile=mem&_mediatype=application/json")
#     link = r.json()["members"][0]["link"]
#     # get link for first collection
#     r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
#     col_link = r2.json()["members"][0]["link"]
#
#     r3 = client.get(f"{col_link}?_profile=alt&_mediatype=text/turtle")
#     assert '<h1>Alternate Profiles</h1>' in r3.text


@pytest.fixture(scope="module")
def an_fc_link(a_dataset_link):
    # get link for first collection
    r2 = client.get(f"{a_dataset_link}/collections?_profile=mem&_mediatype=application/json")
    return r2.json()["members"][0]["link"]


def test_collection_items_default_default(an_fc_link):
    r3 = client.get(f"{an_fc_link}/items")
    assert '<h1>Feature list</h1>' in r3.text


def test_collection_items_mem_json(an_fc_link):
    r3 = client.get(f"{an_fc_link}/items?_profile=mem&_mediatype=application/json")
    assert f'"uri":"http://testserver{an_fc_link}/items?_profile=mem&_mediatype=application/json"' in r3.text


@pytest.fixture(scope="module")
def a_feature_link_and_id(an_fc_link):
    r3 = client.get(f"{an_fc_link}/items?_profile=mem&_mediatype=application/json")
    feature_link = r3.json()["members"][0]["link"]
    feature_id = r3.json()["members"][0]["id"]

    return feature_link, feature_id


def test_feature_default_default(a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r4 = client.get(f"{feature_link}")
    assert f'Feature {feature_id}' in r4.text


def test_feature_default_turtle(a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r4 = client.get(f"{feature_link}?_mediatype=text/turtle")
    assert f'a geo:Feature' in r4.text


def test_feature_alt_default(a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r4 = client.get(f"{feature_link}?_profile=alt")
    assert '<h1>Alternate Profiles</h1>' in r4.text