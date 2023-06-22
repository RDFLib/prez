from pathlib import Path
from typing import Optional

import toml
from pydantic import BaseSettings, root_validator
from rdflib import URIRef
from rdflib.namespace import GEO, DCAT, SKOS, PROF

from prez.reference_data.prez_ns import PREZ


class Settings(BaseSettings):
    """
    sparql_endpoint: Read-only SPARQL endpoint for Prez
    sparql_username: A username for the Prez SPARQL endpoint, if required by the RDF DB
    sparql_password:  A password for the Prez SPARQL endpoint, if required by the RDF DB
    protocol: The protocol used to deliver Prez. Usually 'http', could be 'https'.
    host: Prez' host domain name. Usually 'localhost' but could be anything
    port: The port Prez is made accessible on. Default is 8000, could be 80 or anything else that your system has permission to use
    system_uri: Documentation property. An IRI for the Prez system as a whole. This value appears in the landing page RDF delivered by Prez ('/')
    top_level_classes:
    collection_classes:
    general_classes:
    log_level:
    log_output:
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
    prez_title:
    prez_desc:
    prez_version:
    """

    sparql_endpoint: str
    sparql_username: Optional[str]
    sparql_password: Optional[str]
    sparql_auth: Optional[tuple]
    protocol: str = "http"
    host: str = "localhost"
    port: int = 8000
    curie_separator: str = ":"
    system_uri: Optional[str]
    top_level_classes: Optional[dict]
    collection_classes: Optional[dict]
    general_classes: Optional[dict]
    prez_flavours: Optional[list] = ["SpacePrez", "VocPrez", "CatPrez", "ProfilesPrez"]
    log_level = "INFO"
    log_output = "stdout"
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
    prez_title: Optional[str] = "Prez"
    prez_desc: Optional[str] = (
        "A web framework API for delivering Linked Data. It provides read-only access to "
        "Knowledge Graph data which can be subset according to information profiles."
    )
    prez_version: Optional[str]

    @root_validator()
    def check_endpoint_enabled(cls, values):
        if not values.get("sparql_endpoint"):
            raise ValueError(
                'A SPARQL endpoint must be specified using the "SPARQL_ENDPOINT" environment variable'
            )
        return values

    @root_validator()
    def get_version(cls, values):
        values["prez_version"] = toml.load(
            Path(Path(__file__).parent.parent) / "pyproject.toml"
        )["tool"]["poetry"]["version"]
        return values

    @root_validator()
    def set_system_uri(cls, values):
        if not values.get("system_uri"):
            values["system_uri"] = URIRef(
                f"{values['protocol']}://{values['host']}:{values['port']}"
            )
        return values

    @root_validator()
    def populate_top_level_classes(cls, values):
        values["top_level_classes"] = {
            "Profiles": [
                PROF.Profile,
                PREZ.SpacePrezProfile,
                PREZ.VocPrezProfile,
                PREZ.CatPrezProfile,
            ],
            "SpacePrez": [DCAT.Dataset],
            "VocPrez": [SKOS.ConceptScheme, SKOS.Collection],
            "CatPrez": [DCAT.Catalog],
        }
        return values

    @root_validator()
    def populate_collection_classes(cls, values):
        additional_classes = {
            "Profiles": [],
            "SpacePrez": [GEO.FeatureCollection],
            "VocPrez": [],
            "CatPrez": [DCAT.Resource],
        }
        values["collection_classes"] = {}
        for prez in list(additional_classes.keys()) + ["Profiles"]:
            values["collection_classes"][prez] = (
                values["top_level_classes"].get(prez) + additional_classes[prez]
            )
        return values

    @root_validator()
    def populate_general_classes(cls, values):
        additional_classes = {
            "SpacePrez": [GEO.Feature],
            "VocPrez": [SKOS.Concept],
            "CatPrez": [DCAT.Dataset],
            "Profiles": [PROF.Profile],
        }
        values["general_classes"] = {}
        for prez in list(additional_classes.keys()) + ["Profiles"]:
            values["general_classes"][prez] = (
                values["collection_classes"].get(prez) + additional_classes[prez]
            )
        return values

    @root_validator()
    def populate_sparql_creds(cls, values):
        username = values.get("sparql_username")
        password = values.get("sparql_password")
        if username is not None and password is not None:
            values["sparql_auth"] = (username, password)
        return values


settings = Settings()
