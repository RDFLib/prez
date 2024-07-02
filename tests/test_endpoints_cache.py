from rdflib import Graph

from prez.reference_data.prez_ns import PREZ


def test_purge_cache(client):
    # add some annotations to the cache
    client.get("/catalogs")
    # purge the cache
    response = client.get("/purge-tbox-cache")
    assert response.status_code == 200
    # check that the cache is empty
    r = client.get("/tbox-cache")
    g = Graph().parse(data=r.text)
    assert len(g) == 0


def test_cache(client):
    # add some annotations to the cache
    catalogs = client.get("/catalogs")
    assert catalogs.status_code == 200
    r = client.get("/tbox-cache")
    g = Graph().parse(data=r.text)
    labels = (
        None,
        PREZ.label,
        None,
    )
    descriptions = (
        None,
        PREZ.description,
        None,
    )
    assert len(list(g.triples(labels))) > 0
    assert len(list(g.triples(descriptions))) > 0
