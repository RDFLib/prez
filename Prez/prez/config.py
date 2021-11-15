import os
from pathlib import Path

from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV, OWL, SDO

SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
DATA_URI = os.environ.get("DATA_URI", "http://exampledata.org")
VOCS_TITLE = os.environ.get("VOCS_TITLE", "SURROUND Vocabulary Registry")
VOCS_DESC = os.environ.get("VOCS_DESC", "These vocabs are published by...")
DEBUG = os.environ.get("DEBUG", True)
PORT = os.environ.get("PORT", 8000)
SPARQL_ENDPOINT = os.environ.get(
    "SPARQL_ENDPOINT", "http://localhost:7200/repositories/vocprez-test"
)
SPARQL_USERNAME = os.environ.get("SPARQL_USERNAME", "user")
SPARQL_PASSWORD = os.environ.get("SPARQL_PASSWORD", "password")
TEMPLATES_DIRECTORY = Path(__file__).parent / "templates"
ENABLED_PREZS = ["VocPrez"]  # must use proper capitalisation
TEMPLATE_VOLUME = None
SIDENAV = True
SEARCH_ENDPOINTS = [
    ("self", "Self"),
    ("http://ga.surroundaustralia.com/sparql/", "GA VocPrez"),
    ("http://ggic.surroundaustralia.com/sparql/", "GGIC VocPrez"),
    ("http://dawe.surroundaustralia.com/sparql/", "DAWE VocPrez"),
    ("http://icsm.surroundaustralia.com/sparql/", "ICSM VocPrez"),
    ("http://csiro.surroundaustralia.com/sparql/", "CSIRO VocPrez"),
]
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
