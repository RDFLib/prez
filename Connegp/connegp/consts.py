MEDIATYPE_NAMES = {
    "text/html": "HTML",
    "text/turtle": "Turtle",
    "application/rdf+xml": "RDF/XML",
    "application/ld+json": "JSON-LD",
    "application/json": "JSON",
    "application/n-triples": "N-triples",
}

RDF_MEDIATYPES = [
    "text/turtle",
    "application/rdf+xml",
    "application/ld+json",
    "application/n-triples",
]

RDF_FILE_EXTS = {
    "text/turtle": "ttl",
    "application/rdf+xml": "rdf",
    "application/ld+json": "jsonld",
    "application/n-triples": "nt",
}

RDF_SERIALIZER_TYPES_MAP = {
    "text/turtle": "turtle",
    "text/n3": "n3",
    "application/n-triples": "nt",
    "application/ld+json": "json-ld",
    "application/rdf+xml": "xml",
    # Some common but incorrect mimetypes
    "application/rdf": "xml",
    "application/rdf xml": "xml",
    "application/json": "json-ld",
    "application/ld json": "json-ld",
    "text/ttl": "turtle",
    "text/ntriples": "nt",
    "text/n-triples": "nt",
    "text/plain": "nt",  # text/plain is the old/deprecated mimetype for n-triples
}
