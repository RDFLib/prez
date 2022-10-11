from rdflib import URIRef, Literal

tbox_cache = {
    URIRef("http://www.opengis.net/ont/geosparql#asWKT"): Literal("as WKT"),
    URIRef("http://www.opengis.net/ont/geosparql#hasGeometry"): Literal("has Geometry"),
}

# TODO populate from SPARQL endpoint on startup


def update_tbox_label_cache(graph_iri: URIRef):
    pass
