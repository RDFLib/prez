def test_issue(client):
    r = client.get("/catalogs/ex:cat/collections/ex:res")
    assert r.status_code == 200
