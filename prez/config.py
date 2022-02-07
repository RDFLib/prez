import os
import json

from rdflib import Namespace
from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV, OWL, SDO

GEO = Namespace("http://www.opengis.net/ont/geosparql#")

SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
SYSTEM_INFO = json.loads(
    os.environ.get(
        "SYSTEM_INFO",
        """{
    "Prez": {
        "title": "SURROUND Prez",
        "desc": "Prez demo instance for SURROUND Australia"
    },
    "VocPrez": {
        "title": null,
        "desc": null,
        "data_uri": null
    },
    "CatPrez": {
        "title": null,
        "desc": null,
        "data_uri": null
    },
    "TimePrez": {
        "title": null,
        "desc": null,
        "data_uri": null
    },
    "SpacePrez": {
        "title": "SURROUND Floods",
        "desc": "Floods spatial data",
        "data_uri": "http://exampledata.org"
    }
}""",
    )
)
DEBUG = os.environ.get("DEBUG", True)
DEMO = os.environ.get("DEMO", True)
ALLOW_PARTIAL_RESULTS = os.environ.get("ALLOW_PARTIAL_RESULTS", True)
SPARQL_CREDS = json.loads(
    os.environ.get(
        "SPARQL_CREDS",
        """{
    "VocPrez": {
        "SPARQL_ENDPOINT": null,
        "SPARQL_USERNAME": null,
        "SPARQL_PASSWORD": null
    },
    "CatPrez": {
        "SPARQL_ENDPOINT": null,
        "SPARQL_USERNAME": null,
        "SPARQL_PASSWORD": null
    },
    "TimePrez": {
        "SPARQL_ENDPOINT": null,
        "SPARQL_USERNAME": null,
        "SPARQL_PASSWORD": null
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
