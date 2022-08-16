import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from time import sleep

PREZ_DIR = Path(__file__).parent.parent.absolute() / "prez"
LOCAL_SPARQL_STORE = Path(Path(__file__).parent / "local_sparql_store/store.py")
sys.path.insert(0, str(PREZ_DIR.parent.absolute()))
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def sp_test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3032"])
    sleep(1)
    print("\nDoing config setup")
    # preserve original config file
    shutil.copyfile(PREZ_DIR / "config.py", PREZ_DIR / "config.py.original")

    # alter config file contents
    with open(PREZ_DIR / "config.py") as f:
        config = f.read()
        config = config.replace("Default Prez", "Test Prez")
        config = config.replace("Default SpacePrez", "Test SpacePrez")
        config = config.replace('["VocPrez", "SpacePrez"]', '["SpacePrez"]')
        config = config.replace(
            '"SPACEPREZ_SPARQL_ENDPOINT", ""',
            '"SPACEPREZ_SPARQL_ENDPOINT", "http://localhost:3032/spaceprez"',
        )

    # write altered config contents to config.py
    with open(PREZ_DIR / "config.py", "w") as f:
        f.truncate(0)
        f.write(config)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

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
def an_fc_link(sp_test_client, a_dataset_link):
    # get link for a dataset's collections
    r = sp_test_client.get(
        f"{a_dataset_link}/collections?_profile=mem&_mediatype=application/json"
    )
    return r.json()["members"][0]["link"]


@pytest.fixture(scope="module")
def a_feature_link_and_id(sp_test_client, an_fc_link):
    r = sp_test_client.get(
        f"{an_fc_link}/items?_profile=mem&_mediatype=application/json"
    )
    feature_link = r.json()["members"][0]["link"]
    feature_id = r.json()["members"][0]["id"]

    return feature_link, feature_id


@pytest.fixture(scope="module")
def a_dataset_uri(sp_test_client):
    # get uri for first dataset
    r = sp_test_client.get("/datasets?_profile=mem&_mediatype=application/json")
    return r.json()["members"][0]["uri"]


@pytest.fixture(scope="module")
def an_fc_uri(sp_test_client, a_dataset_link):
    # get uri for a dataset's collections
    r = sp_test_client.get(
        f"{a_dataset_link}/collections?_profile=mem&_mediatype=application/json"
    )
    return r.json()["members"][0]["uri"]


@pytest.fixture(scope="module")
def a_feature_uri(sp_test_client, an_fc_link):
    # get uri for a feature
    r = sp_test_client.get(
        f"{an_fc_link}/items?_profile=mem&_mediatype=application/json"
    )
    return r.json()["members"][0]["uri"]


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
    r = sp_test_client.get(f"{a_dataset_link}")
    assert (
        f'<li class="breadcrumb"><a href="http://testserver{a_dataset_link}">' in r.text
    )


def test_dataset_oai_geojson(sp_test_client, a_dataset_link):
    ds_iri = f"http://testserver{a_dataset_link}?_profile=oai&_mediatype=application/geo+json"
    r = sp_test_client.get(ds_iri)
    j = r.json()
    assert j.get("title") is not None
    assert j.get("geometry") is not None


def test_dataset_default_turtle(sp_test_client, a_dataset_link):
    r2 = sp_test_client.get(f"{a_dataset_link}?_mediatype=text/turtle")
    assert f"a <http://www.w3.org/ns/dcat#Dataset> ;" in r2.text


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


def test_collection_default_default(sp_test_client, an_fc_link):
    r = sp_test_client.get(f"{an_fc_link}")
    assert (
        '<a href="http://www.opengis.net/ont/geosparql#FeatureCollection" target="_blank" >'
        in r.text
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


def test_collection_alt_default(sp_test_client, an_fc_link):
    r = sp_test_client.get(f"{an_fc_link}?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r.text


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


def test_collection_items_default_default(sp_test_client, an_fc_link):
    r = sp_test_client.get(f"{an_fc_link}/items")
    assert "<h1>Feature list</h1>" in r.text


def test_collection_items_mem_json(sp_test_client, an_fc_link):
    r = sp_test_client.get(
        f"{an_fc_link}/items?_profile=mem&_mediatype=application/json"
    )
    assert (
        f'"uri":"http://testserver{an_fc_link}/items?_profile=mem&_mediatype=application/json"'
        in r.text
    )


def test_feature_default_default(sp_test_client, a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r = sp_test_client.get(f"{feature_link}")
    assert f' <p>Instance URI: <a href="http://testserver{feature_link}">' in r.text


def test_feature_default_geojson(sp_test_client, a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r = sp_test_client.get(f"{feature_link}?_mediatype=application/geo+json")
    j = r.json()
    assert j.get("geometry") is not None


def test_feature_default_geojson_given_v_generated(sp_test_client):
    # checks that the get GeoJSON function is trying to return given GeoJSON
    # but, if not finding it, calculates it from WKT which must be present
    r = sp_test_client.get(
        "http://testserver/dataset/geofabric/collections/catchments/items/cabbage-tree?_mediatype=application/geo+json"
    )
    assert len(r.json()["geometry"]["coordinates"][0]) == 16

    r = sp_test_client.get(
        "http://testserver/dataset/geofabric/collections/catchments/items/cabbage-tree-geojson?_mediatype=application/geo+json"
    )
    assert len(r.json()["geometry"]["coordinates"][0]) == 14


def test_feature_default_turtle(sp_test_client, a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r = sp_test_client.get(f"{feature_link}?_mediatype=text/turtle")
    assert f"> a geo:Feature" in r.text


def test_feature_alt_default(sp_test_client, a_feature_link_and_id):
    feature_link, feature_id = a_feature_link_and_id

    r = sp_test_client.get(f"{feature_link}?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r.text


def test_object_endpoint_dataset(sp_test_client, a_dataset_uri):
    r = sp_test_client.get(f"/object?uri={a_dataset_uri}")
    assert f'<a href="{a_dataset_uri}"' in r.text


def test_object_endpoint_feature_collection(sp_test_client, an_fc_uri):
    r = sp_test_client.get(f"/object?uri={an_fc_uri}")
    assert f'<a href="{an_fc_uri}"' in r.text


def test_object_endpoint_feature(sp_test_client, a_feature_uri):
    r = sp_test_client.get(f"/object?uri={a_feature_uri}")
    assert f'<a href="{a_feature_uri}"' in r.text
