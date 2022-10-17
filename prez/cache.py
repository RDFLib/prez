from rdflib import URIRef, Literal, Graph

tbox_cache = Graph()
tbox_cache.add(
    (
        URIRef("http://www.w3.org/ns/dcat#Dataset"),
        URIRef("http://www.w3.org/2000/01/rdf-schema#label"),
        Literal("Dataset"),
    )
)

missing_annotations = []
