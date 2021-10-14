import os
from pathlib import Path

from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV

SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
DATA_URI = os.environ.get("DATA_URI", "http://exampledata.org")
DEBUG = os.environ.get("DEBUG", True)
PORT = os.environ.get("PORT", 8000)
SPARQL_ENDPOINT = os.environ.get(
    "SPARQL_ENDPOINT", "http://localhost:7200/repositories/vocprez-test"
)
SPARQL_USERNAME = os.environ.get("SPARQL_USERNAME", "user")
SPARQL_PASSWORD = os.environ.get("SPARQL_PASSWORD", "password")
TEMPLATES_DIRECTORY = Path(__file__).parent / "templates"
ENABLED_PREZS = [
    "vocprez"
]

NAMESPACE_PREFIXES = {
    str(SKOS): "skos",
    str(RDF): "rdf",
    str(RDFS): "rdfs",
    str(DCAT): "dcat",
    str(DCTERMS): "dcterms",
    str(PROV): "prov",
}