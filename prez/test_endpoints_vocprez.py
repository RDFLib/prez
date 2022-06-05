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


def test_home_alt_turtle():
    r = client.get("/?_profile=alt&_mediatype=text/turtle")
    assert r.status_code == 200
    assert "<h1>Alternate Profiles</h1>" in r.text
