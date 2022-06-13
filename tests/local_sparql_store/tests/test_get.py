import httpx


def test_home():
    r = httpx.get("http://localhost:3030")
    assert r.status_code == 200


def test_vocprez_home():
    r = httpx.get("http://localhost:3030/vocprez")
    assert r.status_code == 200


def test_spaceprez_home():
    r = httpx.get("http://localhost:3030/spaceprez")
    assert r.status_code == 200


def test_unknown_endpoint():
    r = httpx.get("http://localhost:3030/xxx")
    assert r.status_code == 404


def test_vocprez_query_good():
    r = httpx.get("http://localhost:3030/vocprez?query=PREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0AASK%0AWHERE%20{%0A%20%20%20%20%3Fc%20a%20skos%3AConcept%20%3B%0A%20%20%20%20%20%20%20skos%3AprefLabel%20%3Fpl%20.%0A}%0ALIMIT%205")
    assert r.status_code == 200


def test_vocprez_query_bad():
    r = httpx.get("http://localhost:3030/vocprez?query=ddddPREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0AASK%0AWHERE%20{%0A%20%20%20%20%3Fc%20a%20skos%3AConcept%20%3B%0A%20%20%20%20%20%20%20skos%3AprefLabel%20%3Fpl%20.%0A}%0ALIMIT%205")
    assert r.status_code == 400
    assert r.text.startswith("Your SPARQL query could not be interpreted")
