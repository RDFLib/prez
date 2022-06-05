from fastapi.testclient import TestClient
from prez.app import app


client = TestClient(app)


def test_home_default_default():
    r = client.get("/")
    assert r.status_code == 200
    assert "<h1>System Home</h1>" in r.text


def test_home_alt_html():
    r = client.get("/?_profile=alt")
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


def test_dataset_default_default():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]

    r2 = client.get(f"{link}")
    assert f'<li class="breadcrumb"><a href="http://testserver{link}">' in r2.text


def test_dataset_default_turtle():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]

    r2 = client.get(f"{link}?_mediatype=text/turtle")
    assert f'a dcat:Dataset ;' in r2.text


def test_dataset_alt_html():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]

    r2 = client.get(f"{link}?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r2.text


def test_dataset_alt_turtle():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]

    r2 = client.get(f"{link}?_profile=alt&_mediatype=text/turtle")
    assert "a rdfs:Resource ;" in r2.text


def test_dataset_collections_default_default():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]

    r2 = client.get(f"{link}/collections")
    assert f'<h1>FeatureCollection list</h1>' in r2.text


def test_dataset_collections_mem_json():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]

    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
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


def test_collection_items_default_default():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]

    r3 = client.get(f"{col_link}/items")
    assert '<h1>Feature list</h1>' in r3.text


def test_collection_items_mem_json():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]

    r3 = client.get(f"{col_link}/items?_profile=mem&_mediatype=application/json")
    assert f'"uri":"http://testserver{col_link}/items?_profile=mem&_mediatype=application/json"' in r3.text


def test_feature_default_default():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]
    # get link for first feature
    r3 = client.get(f"{col_link}/items?_profile=mem&_mediatype=application/json")
    feature_link = r3.json()["members"][0]["link"]
    feature_id = r3.json()["members"][0]["id"]

    r4 = client.get(f"{feature_link}")
    assert f'Feature {feature_id}' in r4.text


def test_feature_default_turtle():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]
    # get link for first feature
    r3 = client.get(f"{col_link}/items?_profile=mem&_mediatype=application/json")
    feature_link = r3.json()["members"][0]["link"]
    feature_id = r3.json()["members"][0]["id"]

    r4 = client.get(f"{feature_link}?_mediatype=text/turtle")
    assert f'a geo:Feature' in r4.text


def test_feature_alt_default():
    # get link for first dataset
    r = client.get("/datasets?_profile=mem&_mediatype=application/json")
    link = r.json()["members"][0]["link"]
    # get link for first collection
    r2 = client.get(f"{link}/collections?_profile=mem&_mediatype=application/json")
    col_link = r2.json()["members"][0]["link"]
    # get link for first feature
    r3 = client.get(f"{col_link}/items?_profile=mem&_mediatype=application/json")
    feature_link = r3.json()["members"][0]["link"]
    feature_id = r3.json()["members"][0]["id"]

    r4 = client.get(f"{feature_link}?_profile=alt")
    assert '<h1>Alternate Profiles</h1>' in r4.text