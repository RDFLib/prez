from fastapi.testclient import TestClient
from prez.app import app
import re
import pytest


client = TestClient(app)


def test_home_default_default():
    r = client.get("/")
    assert "<h1>System Home</h1>" in r.text


def test_home_default_turtle():
    r = client.get("/?_mediatype=text/turtle")
    assert "a dcat:Dataset" in r.text


def test_home_alt_html():
    r = client.get("/?_profile=alt")
    assert "<h1>Alternate Profiles</h1>" in r.text


def test_home_alt_turtle():
    r = client.get("/?_profile=alt&_mediatype=text/turtle")
    assert "a rdfs:Resource" in r.text


def test_vocabs_default_default():
    r = client.get("/vocab")
    assert "Concept Scheme list" in r.text


# def test_vocabs_default_turtle():
#     r = client.get("/vocabs?_mediatype=text/turtle")
#     assert "a dcat:Dataset" in r.text


def test_vocabs_dd_json():
    r = client.get("/vocab?_profile=dd&_mediatype=application/json")
    assert '[{"uri":"' in r.text


@pytest.fixture(scope="module")
def a_vocab_id():
    r = client.get("/vocab")
    return re.search(r'<a href="/vocab/(.*)">', r.text)[1]


def test_vocab_default_default(a_vocab_id):
    r2 = client.get(f"/vocab/{a_vocab_id}?_mediatype=text/html")  # TODO: work out why HTML has to be specified here?
    assert '<li class="breadcrumb"><a href="http://testserver/vocab/CI_DateTypeCode">' in r2.text


def test_vocab_default_turtle(a_vocab_id):
    r2 = client.get(f"/vocab/{a_vocab_id}?_mediatype=text/turtle")
    assert 'a skos:ConceptScheme' in r2.text


def test_vocab_alt_default(a_vocab_id):
    r2 = client.get(f"/vocab/{a_vocab_id}?_profile=alt")
    assert 'Alternate Profiles' in r2.text


def test_vocab_alt_turtle(a_vocab_id):
    r2 = client.get(f"/vocab/{a_vocab_id}?_profile=alt&_mediatype=text/turtle")
    assert 'a rdfs:Resource' in r2.text


def test_vocab_dd_json(a_vocab_id):
    r2 = client.get(f"/vocab/{a_vocab_id}?_profile=dd&_mediatype=application/json")
    assert '[{"uri":"http' in r2.text


@pytest.fixture(scope="module")
def a_vocab_id_and_a_concept_id(a_vocab_id):
    # get the first concept endpoint
    r2 = client.get(f"/vocab/{a_vocab_id}?_mediatype=text/html")
    patt = f'<a href="http://testserver/vocab/{a_vocab_id}/(.*)">'
    return (a_vocab_id, re.search(patt, r2.text)[1])


def test_concept_default_default(a_vocab_id_and_a_concept_id):
    a_vocab_id, a_concept_id = a_vocab_id_and_a_concept_id

    # TODO: should not have to specify vocpub for default
    r3 = client.get(f"/vocab/{a_vocab_id}/{a_concept_id}?_profile=vocpub&_mediatype=text/html")
    assert '<a href="http://www.w3.org/2004/02/skos/core#Concept" target="_blank" >' in r3.text


def test_concept_default_turtle(a_vocab_id_and_a_concept_id):
    a_vocab_id, a_concept_id = a_vocab_id_and_a_concept_id

    r3 = client.get(f"/vocab/{a_vocab_id}/{a_concept_id}?_profile=vocpub&_mediatype=text/turtle")
    assert 'a skos:Concept' in r3.text


def test_concept_alt_default(a_vocab_id_and_a_concept_id):
    a_vocab_id, a_concept_id = a_vocab_id_and_a_concept_id

    r3 = client.get(f"/vocab/{a_vocab_id}/{a_concept_id}?_profile=alt")
    print(f"/vocab/{a_vocab_id}/{a_concept_id}?_profile=alt")
    assert '<h1>Alternate Profiles</h1>' in r3.text


# def test_concept_alt_turtle(a_vocab_id_and_a_concept_id):
#     a_vocab_id, a_concept_id = a_vocab_id_and_a_concept_id
#
#     r3 = client.get(f"/vocab/{a_vocab_id}/{a_concept_id}?_profile=alt&_mediatype=text/turtle")
#     assert '<h1>Alternate Profiles</h1>' in r3.text