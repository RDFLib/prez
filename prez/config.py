import os
import json

from rdflib import Graph, URIRef, Literal, BNode, Namespace
from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV, OWL, SDO, XSD

PROF = Namespace("http://www.w3.org/ns/dx/prof/")
PREZ = Namespace("https://surroundaustralia.com/prez/")
GEO = Namespace("http://www.opengis.net/ont/geosparql#")

SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
SYSTEM_INFO = json.loads(
    os.environ.get(
        "SYSTEM_INFO",
        """{
    "Prez": {
        "title": "Prez",
        "desc": "Prez default"
    },
    "VocPrez": {
        "title": "VocPrez",
        "desc": "VocPrez default",
        "data_uri": "http://exampledata.org"
    },
    "CatPrez": {
        "title": "",
        "desc": "",
        "data_uri": ""
    },
    "TimePrez": {
        "title": "",
        "desc": "",
        "data_uri": ""
    },
    "SpacePrez": {
        "title": "SpacePrez",
        "desc": "Spatial default",
        "data_uri": "http://exampledata.org"
    }
}""",
    )
)

PREZ_TITLE = os.environ.get("PREZ_TITLE", "Default Prez")
PREZ_DESC = os.environ.get("PREZ_DESC", "Prez default description")

VOCPREZ_TITLE = os.environ.get("VOCPREZ_TITLE", "Default VocPrez")
VOCPREZ_DESC = os.environ.get("VOCPREZ_DESC", "VocPrez default description")
VOCPREZ_DATA_URI = os.environ.get("VOCPREZ_DATA_URI", "http://exampledata.org")

SPACEPREZ_TITLE = os.environ.get("SPACEPREZ_TITLE", "Default SpacePrez")
SPACEPREZ_DESC = os.environ.get("SPACEPREZ_DESC", "SpacePrez default description")
SPACEPREZ_DATA_URI = os.environ.get("SPACEPREZ_DATA_URI", "http://exampledata.org")

# SPARQL credentials
VOCPREZ_SPARQL_ENDPOINT = os.environ.get("VOCPREZ_SPARQL_ENDPOINT", "")
VOCPREZ_SPARQL_USERNAME = os.environ.get("VOCPREZ_SPARQL_USERNAME", "")
VOCPREZ_SPARQL_PASSWORD = os.environ.get("VOCPREZ_SPARQL_PASSWORD", "")

SPACEPREZ_SPARQL_ENDPOINT = os.environ.get("SPACEPREZ_SPARQL_ENDPOINT", "")
SPACEPREZ_SPARQL_USERNAME = os.environ.get("SPACEPREZ_SPARQL_USERNAME", "")
SPACEPREZ_SPARQL_PASSWORD = os.environ.get("SPACEPREZ_SPARQL_PASSWORD", "")

TIMEPREZ_SPARQL_ENDPOINT = os.environ.get("TIMEPREZ_SPARQL_ENDPOINT", "")
TIMEPREZ_SPARQL_USERNAME = os.environ.get("TIMEPREZ_SPARQL_USERNAME", "")
TIMEPREZ_SPARQL_PASSWORD = os.environ.get("TIMEPREZ_SPARQL_PASSWORD", "")

CATPREZ_SPARQL_ENDPOINT = os.environ.get("CATPREZ_SPARQL_ENDPOINT", "")
CATPREZ_SPARQL_USERNAME = os.environ.get("CATPREZ_SPARQL_USERNAME", "")
CATPREZ_SPARQL_PASSWORD = os.environ.get("CATPREZ_SPARQL_PASSWORD", "")

DEBUG = os.environ.get("DEBUG", True)
DEMO = os.environ.get("DEMO", True)
ALLOW_PARTIAL_RESULTS = os.environ.get("ALLOW_PARTIAL_RESULTS", True)
SPARQL_CREDS = json.loads(
    os.environ.get(
        "SPARQL_CREDS",
        """{
    "VocPrez": {
        "SPARQL_ENDPOINT": "http://localhost:3030/surround-vocabs",
        "SPARQL_USERNAME": "",
        "SPARQL_PASSWORD": ""
    },
    "CatPrez": {
        "SPARQL_ENDPOINT": "",
        "SPARQL_USERNAME": "",
        "SPARQL_PASSWORD": ""
    },
    "TimePrez": {
        "SPARQL_ENDPOINT": "",
        "SPARQL_USERNAME": "",
        "SPARQL_PASSWORD": ""
    },
    "SpacePrez": {
        "SPARQL_ENDPOINT": "http://localhost:3030/floods-2",
        "SPARQL_USERNAME": "",
        "SPARQL_PASSWORD": ""
    }
}""",
    )
)
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

USE_PID_LINKS = False
