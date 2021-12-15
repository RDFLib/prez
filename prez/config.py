import os
import json

from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV, OWL, SDO

SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
DATA_URI = os.environ.get("DATA_URI", "http://exampledata.org")
SYSTEM_INFO = json.loads(os.environ.get("SYSTEM_INFO", '''{
    "Prez": {
        "title": "SURROUND Vocabulary Registry",
        "desc": "These vocabs are published by..."
    },
    "VocPrez": {
        "title": "SURROUND Vocabulary Registry",
        "desc": "These vocabs are published by..."
    },
    "CatPrez": {
        "title": null,
        "desc": null
    },
    "TimePrez": {
        "title": null,
        "desc": null
    },
    "SpacePrez": {
        "title": null,
        "desc": null
    }
}'''))
DEBUG = os.environ.get("DEBUG", True)
DEMO = os.environ.get("DEMO", True)
SPARQL_ENDPOINT = os.environ.get(
    "SPARQL_ENDPOINT", "http://localhost:3030/surround-vocabs"
)
SPARQL_USERNAME = os.environ.get("SPARQL_USERNAME", "")
SPARQL_PASSWORD = os.environ.get("SPARQL_PASSWORD", "")
ENABLED_PREZS = json.loads(os.environ.get("ENABLED_PREZS", '["VocPrez"]'))  # must use proper capitalisation
THEME_VOLUME = os.environ.get("THEME_VOLUME", None)
SIDENAV = os.environ.get("SIDENAV", "False") == "True"
SEARCH_ENDPOINTS = [{"name": "Self", "url": "self"}] + json.loads(os.environ.get("SEARCH_ENDPOINTS", '''[
    {"name": "GA VocPrez", "url": "http://ga.surroundaustralia.com/sparql/"},
    {"name": "GSQ VocPrez", "url": "http://gsq.surroundaustralia.com/sparql/"},
    {"name": "GGIC VocPrez", "url": "http://ggic.surroundaustralia.com/sparql/"},
    {"name": "DAWE VocPrez", "url": "http://dawe.surroundaustralia.com/sparql/"},
    {"name": "CSIRO VocPrez", "url": "http://csiro.surroundaustralia.com/sparql/"},
    {"name": "ICSM VocPrez", "url": "http://icsm.surroundaustralia.com/sparql/"},
    {"name": "GSRSD VocPrez", "url": "http://gsrsd.surroundaustralia.com/sparql/"}
]'''))

NAMESPACE_PREFIXES = {
    str(SKOS): "skos",
    str(RDF): "rdf",
    str(RDFS): "rdfs",
    str(DCAT): "dcat",
    str(DCTERMS): "dcterms",
    str(PROV): "prov",
    str(OWL): "owl",
    str(SDO): "sdo",
}
