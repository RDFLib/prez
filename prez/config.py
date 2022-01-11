import os
import json

from rdflib import Namespace
from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV, OWL, SDO

GEO = Namespace("http://www.opengis.net/ont/geosparql#")

SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
DATA_URI = os.environ.get("DATA_URI", "http://exampledata.org")
SYSTEM_INFO = json.loads(
    os.environ.get(
        "SYSTEM_INFO",
        """{
    "Prez": {
        "title": "SURROUND Floods",
        "desc": "Floods spatial data"
    },
    "VocPrez": {
        "title": null,
        "desc": null
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
        "title": "SURROUND Floods",
        "desc": "Floods spatial data"
    }
}""",
    )
)
DEBUG = os.environ.get("DEBUG", True)
DEMO = os.environ.get("DEMO", True)
SPARQL_ENDPOINT = os.environ.get("SPARQL_ENDPOINT", "http://localhost:3030/floods")
SPARQL_USERNAME = os.environ.get("SPARQL_USERNAME", "")
SPARQL_PASSWORD = os.environ.get("SPARQL_PASSWORD", "")
ENABLED_PREZS = json.loads(
    os.environ.get("ENABLED_PREZS", '["SpacePrez"]')
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
