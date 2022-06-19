import httpx


def test_home():
    r = httpx.post("http://localhost:3030")
    assert r.status_code == 200


def test_vocprez_query():
    r = httpx.post(
        "http://localhost:3030/vocprez", data="SELECT * WHERE {?c a skos:Concept}"
    )
    assert r.status_code == 200


def test_spaceprez_query():
    r = httpx.post(
        "http://localhost:3030/spaceprez", data="SELECT * WHERE {?c a dcat:Dataset}"
    )
    assert r.status_code == 200


def test_unknown_endpoint():
    r = httpx.post("http://localhost:3030/xxx")
    assert r.status_code == 404
