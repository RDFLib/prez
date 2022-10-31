# import json
import os

# from functools import cache
# from pathlib import Path
#
# from rdflib import Namespace, Graph, URIRef, Literal
# from rdflib.namespace import SKOS, RDF, DCTERMS, RDFS, DCAT, PROV, OWL, SDO, XSD
#
# PROF = Namespace("http://www.w3.org/ns/dx/prof/")
# PREZ = Namespace("https://surroundaustralia.com/prez/")
# GEO = Namespace("http://www.opengis.net/ont/geosparql#")
# DASH = Namespace("http://datashapes.org/dash#")
# SH = Namespace("http://www.w3.org/ns/shacl#")
#
# SYSTEM_URI = os.environ.get("SYSTEM_URI", "localhost")
#
# PREZ_TITLE = os.environ.get("PREZ_TITLE", "Test Prez")
# PREZ_DESC = os.environ.get("PREZ_DESC", "Prez default description")
#
# CATPREZ_TITLE = os.environ.get("CATPREZ_TITLE", "Default CatPrez")
# CATPREZ_DESC = os.environ.get("CATPREZ_DESC", "CatPrez default description")
# CATPREZ_DATA_URI = os.environ.get("CATPREZ_DATA_URI", "http://exampledata.org")
#
# VOCPREZ_TITLE = os.environ.get("VOCPREZ_TITLE", "Default VocPrez")
# VOCPREZ_DESC = os.environ.get("VOCPREZ_DESC", "VocPrez default description")
# VOCPREZ_DATA_URI = os.environ.get("VOCPREZ_DATA_URI", "http://exampledata.org")
#
# SPACEPREZ_TITLE = os.environ.get("SPACEPREZ_TITLE", "Test SpacePrez")
# SPACEPREZ_DESC = os.environ.get("SPACEPREZ_DESC", "SpacePrez default description")
# SPACEPREZ_DATA_URI = os.environ.get("SPACEPREZ_DATA_URI", "http://exampledata.org")
#
# # SPARQL credentials
# CATPREZ_SPARQL_ENDPOINT = os.environ.get("CATPREZ_SPARQL_ENDPOINT", "")
# CATPREZ_SPARQL_USERNAME = os.environ.get("CATPREZ_SPARQL_USERNAME", "")
# CATPREZ_SPARQL_PASSWORD = os.environ.get("CATPREZ_SPARQL_PASSWORD", "")
#
# VOCPREZ_SPARQL_ENDPOINT = os.environ.get("VOCPREZ_SPARQL_ENDPOINT", "")
# VOCPREZ_SPARQL_USERNAME = os.environ.get("VOCPREZ_SPARQL_USERNAME", "")
# VOCPREZ_SPARQL_PASSWORD = os.environ.get("VOCPREZ_SPARQL_PASSWORD", "")
#
# SPACEPREZ_SPARQL_ENDPOINT = os.environ.get(
#     "SPACEPREZ_SPARQL_ENDPOINT", "http://localhost:3032/spaceprez"
# )
# SPACEPREZ_SPARQL_USERNAME = os.environ.get("SPACEPREZ_SPARQL_USERNAME", "")
# SPACEPREZ_SPARQL_PASSWORD = os.environ.get("SPACEPREZ_SPARQL_PASSWORD", "")
#
# TIMEPREZ_SPARQL_ENDPOINT = os.environ.get("TIMEPREZ_SPARQL_ENDPOINT", "")
# TIMEPREZ_SPARQL_USERNAME = os.environ.get("TIMEPREZ_SPARQL_USERNAME", "")
# TIMEPREZ_SPARQL_PASSWORD = os.environ.get("TIMEPREZ_SPARQL_PASSWORD", "")
#
# DEBUG = os.environ.get("DEBUG", True)
# DEMO = os.environ.get("DEMO", True)
# ALLOW_PARTIAL_RESULTS = os.environ.get("ALLOW_PARTIAL_RESULTS", True)
#
# ENABLED_PREZS = os.environ.get("ENABLED_PREZS", "SpacePrez, VocPrez")
# THEME_VOLUME = os.environ.get("THEME_VOLUME", None)
# SIDENAV = os.environ.get("SIDENAV", "False") == "True"
# SEARCH_ENDPOINTS = [{"name": "Self", "url": "self"}] + json.loads(
#     os.environ.get(
#         "SEARCH_ENDPOINTS",
#         """[]""",
#     )
# )
#
# NAMESPACE_PREFIXES = {
#     str(SKOS): "skos",
#     str(RDF): "rdf",
#     str(RDFS): "rdfs",
#     str(DCAT): "dcat",
#     str(DCTERMS): "dcterms",
#     str(PROV): "prov",
#     str(OWL): "owl",
#     str(SDO): "sdo",
#     str(GEO): "geo",
# }
#
# USE_PID_LINKS = False
#
# # available properties for CQL search
# CQL_PROPS = {
#     "title": {
#         "title": "Title",
#         "description": "The title of a geo:Feature",
#         "type": "string",
#     },
#     "desc": {
#         "title": "Description",
#         "description": "The description of a geo:Feature",
#         "type": "string",
#     },
# }
#
#
# @cache
# def get_version():
#     for line in open(Path(__file__).parent.parent / "pyproject.toml").readlines():
#         if line.startswith("version = "):
#             return line.split('"')[1]
#
#
# VERSION = get_version()
from typing import Optional

from pydantic import (
    BaseSettings,
    PyObject,
    validator,
    root_validator,
)


class Settings(BaseSettings):
    spaceprez_sparql_endpoint: Optional[str]
    catprez_sparql_endpoint: Optional[str]
    vocprez_sparql_endpoint: Optional[str]
    spaceprez_sparql_username: Optional[str]
    catprez_sparql_username: Optional[str]
    vocprez_sparql_username: Optional[str]
    spaceprez_sparql_password: Optional[str]
    catprez_sparql_password: Optional[str]
    vocprez_sparql_password: Optional[str]
    system_uri: str = "localhost"
    enabled_prezs: str = "SpacePrez, VocPrez"
    cql_props: dict = {
        "title": {
            "title": "Title",
            "description": "The title of a geo:Feature",
            "type": "string",
        },
        "desc": {
            "title": "Description",
            "description": "The description of a geo:Feature",
            "type": "string",
        },
    }

    @root_validator()
    def check_endpoints(cls, values):
        if (
            (values.get("spaceprez_sparql_endpoint") is None)
            and (values.get("catprez_sparql_endpoint") is None)
            and (values.get("vocprez_sparql_endpoint") is None)
        ):
            raise ValueError(
                "one or more of spaceprez, vocprez, or catprez SPARQL endpoints are required"
            )
        return values

    @root_validator()  # TODO refactor as JSON config
    def populate_sparql_creds(cls, values):
        values["sparql_creds"] = {
            "CatPrez": {},
            "VocPrez": {},
            "SpacePrez": {},
        }
        for prez in values["enabled_prezs"].split("|"):
            for attr in ["endpoint", "username", "password"]:
                key = f"{prez.lower()}_sparql_{attr}"
                value = values[key]
                if value:
                    values["sparql_creds"][prez][attr] = value
        return values
