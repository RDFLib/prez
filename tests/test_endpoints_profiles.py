from rdflib import Graph, URIRef
from rdflib.namespace import PROF, RDF


def test_profile(client_no_override):
    r = client_no_override.get("/profiles?limit=50")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/profile/prez"), RDF.type, PROF.Profile) in g


def test_ogcprez_profile(client_no_override):
    r = client_no_override.get("/profiles/prez:OGCRecordsProfile")
    g = Graph().parse(data=r.text)
    assert (URIRef("https://prez.dev/OGCRecordsProfile"), RDF.type, PROF.Profile) in g
