from rdflib import Graph, URIRef
from rdflib.namespace import RDF, PROF


def test_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/profile/prez"), RDF.type, PROF.Profile) in g


def test_ogcprez_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles/prez:OGCRecordsProfile")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/OGCRecordsProfile"), RDF.type, PROF.Profile) in g


def test_sp_profile(client):
    # check the example remote profile is loaded
    r = client.get("/profiles/prez:SpacePrezProfile")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/SpacePrezProfile"), RDF.type, PROF.Profile) in g

