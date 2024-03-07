from rdflib import Graph


def test_reset_cache(client):
    client.get("/reset-tbox-cache")
    r = client.get("/tbox-cache")
    g = Graph().parse(data=r.text)
    assert len(g) > 6000  # cache expands as tests are run


def test_cache(client):
    r = client.get("/tbox-cache")
    g = Graph().parse(data=r.text)
    assert len(g) > 6000  # cache expands as tests are run
