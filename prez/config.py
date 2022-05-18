import os
import json

from rdflib import Namespace
from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV, OWL, SDO

GEO = Namespace("http://www.opengis.net/ont/geosparql#")

SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
# info
PREZ_TITLE = os.environ.get("PREZ_TITLE", "SURROUND Prez")
PREZ_DESC = os.environ.get("PREZ_DESC", "Prez demo instance for SURROUND Australia")
VOCPREZ_TITLE = os.environ.get("VOCPREZ_TITLE", "SURROUND Vocabs")
VOCPREZ_DESC = os.environ.get("VOCPREZ_DESC", "Demo vocabularies")
VOCPREZ_DATA_URI = os.environ.get("VOCPREZ_DATA_URI", "http://exampledata.org")
SPACEPREZ_TITLE = os.environ.get("SPACEPREZ_TITLE", "SURROUND Spatial Data")
SPACEPREZ_DESC = os.environ.get("SPACEPREZ_DESC", "Floods spatial data")
SPACEPREZ_DATA_URI = os.environ.get("SPACEPREZ_DATA_URI", "http://exampledata.org")

# SPARQL credentials
VOCPREZ_SPARQL_ENDPOINT = os.environ.get("VOCPREZ_SPARQL_ENDPOINT", "http://localhost:3030/surround-vocabs")
VOCPREZ_SPARQL_USERNAME = os.environ.get("VOCPREZ_SPARQL_USERNAME", "")
VOCPREZ_SPARQL_PASSWORD = os.environ.get("VOCPREZ_SPARQL_PASSWORD", "")
SPACEPREZ_SPARQL_ENDPOINT = os.environ.get("SPACEPREZ_SPARQL_ENDPOINT", "http://localhost:3030/floods-2")
SPACEPREZ_SPARQL_USERNAME = os.environ.get("SPACEPREZ_SPARQL_USERNAME", "")
SPACEPREZ_SPARQL_PASSWORD = os.environ.get("SPACEPREZ_SPARQL_PASSWORD", "")

DEBUG = os.environ.get("DEBUG", True)
DEMO = os.environ.get("DEMO", True)
ALLOW_PARTIAL_RESULTS = os.environ.get("ALLOW_PARTIAL_RESULTS", True)
ENABLED_PREZS = json.loads(
    os.environ.get("ENABLED_PREZS", '["vocprez", "spaceprez"]')
)  # must use proper capitalisation
THEME_VOLUME = os.environ.get("THEME_VOLUME", None)
SIDENAV = os.environ.get("SIDENAV", "False") == "True"
SEARCH_ENDPOINTS = [{"name": "Self", "url": "self"}] + json.loads(
    os.environ.get(
        "SEARCH_ENDPOINTS",
        """[]""",
    )
)

NAMESPACE_PREFIXES = {
    str(SKOS): "skos",
    str(RDF): "rdf",
    str(RDFS): "rdfs",
    str(DCAT): "dcat",
    str(DCTERMS): "dcterms",
    str(PROV): "prov",
    str(OWL): "owl",
    str(SDO): "sdo",
    str(GEO): "geo",
}
