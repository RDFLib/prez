from os import environ
from pathlib import Path
from typing import Optional

import toml
from pydantic import BaseSettings, root_validator
from rdflib import URIRef, DCTERMS, RDFS, SDO
from rdflib.namespace import SKOS

from prez.reference_data.prez_ns import REG


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
    base_classes:
    log_level:
    log_output:
    prez_title:
    prez_desc:
    prez_version:
    """

    sparql_endpoint: Optional[str] = None
    sparql_username: Optional[str] = None
    sparql_password: Optional[str] = None
    sparql_auth: Optional[tuple]
    protocol: str = "http"
    host: str = "localhost"
    port: int = 8000
    curie_separator: str = ":"
    system_uri: Optional[str]
    top_level_classes: Optional[dict]
    collection_classes: Optional[dict]
    order_lists_by_label: bool = True
    base_classes: Optional[dict]
    prez_flavours: Optional[list] = ["SpacePrez", "VocPrez", "CatPrez", "ProfilesPrez"]
    label_predicates = [SKOS.prefLabel, DCTERMS.title, RDFS.label, SDO.name]
    description_predicates = [SKOS.definition, DCTERMS.description, SDO.description]
    provenance_predicates = [DCTERMS.provenance]
    other_predicates = [SDO.color, REG.status]
    sparql_timeout = 30.0
    sparql_repo_type: str = "remote"

    log_level = "INFO"
    log_output = "stdout"
    prez_title: Optional[str] = "Prez"
    prez_desc: Optional[str] = (
        "A web framework API for delivering Linked Data. It provides read-only access to "
        "Knowledge Graph data which can be subset according to information profiles."
    )
    prez_version: Optional[str]
    disable_prefix_generation: bool = False

    @root_validator()
    def get_version(cls, values):
        version = environ.get("PREZ_VERSION")
        values["prez_version"] = version

        if version is None or version == "":
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


settings = Settings()
