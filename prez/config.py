from os import environ
from pathlib import Path
from typing import Optional, List, Tuple

import toml
from pydantic import root_validator
from pydantic_settings import BaseSettings
from rdflib import URIRef, DCTERMS, RDFS, SDO
from rdflib.namespace import SKOS

from prez.reference_data.prez_ns import REG, EP


class Settings(BaseSettings):
    """
    sparql_endpoint: Read-only SPARQL endpoint for Prez
    sparql_username: A username for the Prez SPARQL endpoint, if required by the RDF DB
    sparql_password:  A password for the Prez SPARQL endpoint, if required by the RDF DB
    protocol: The protocol used to deliver Prez. Usually 'http', could be 'https'.
    host: Prez' host domain name. Usually 'localhost' but could be anything
    port: The port Prez is made accessible on. Default is 8000, could be 80 or anything else that your system has permission to use
    system_uri: Documentation property. An IRI for the Prez system as a whole. This value appears in the landing page RDF delivered by Prez ('/')
    log_level:
    log_output:
    prez_title:
    prez_desc:
    prez_version:
    """

    sparql_endpoint: Optional[str] = None
    sparql_username: Optional[str] = None
    sparql_password: Optional[str] = None
    protocol: str = "http"
    host: str = "localhost"
    port: int = 8000
    curie_separator: str = ":"
    system_uri: Optional[str] = f"{protocol}://{host}:{port}"
    order_lists_by_label: bool = True
    label_predicates: Optional[List[URIRef]] = [
        SKOS.prefLabel,
        DCTERMS.title,
        RDFS.label,
        SDO.name,
    ]
    description_predicates: Optional[List[URIRef]] = [
        SKOS.definition,
        DCTERMS.description,
        SDO.description,
    ]
    provenance_predicates: Optional[List[URIRef]] = [DCTERMS.provenance]
    other_predicates: Optional[List[URIRef]] = [
        SDO.color,
        REG.status,
        SKOS.narrower,
        SKOS.broader,
    ]
    sparql_repo_type: str = "remote"
    sparql_timeout: int = 30
    log_level: str = "INFO"
    log_output: str = "stdout"
    prez_title: Optional[str] = "Prez"
    prez_desc: Optional[str] = (
        "A web framework API for delivering Linked Data. It provides read-only access to "
        "Knowledge Graph data which can be subset according to information profiles."
    )
    prez_version: Optional[str] = None
    disable_prefix_generation: bool = False
    default_language: str = "en"
    default_search_predicates: Optional[List[URIRef]] = [
        RDFS.label,
        SKOS.prefLabel,
        SDO.name,
        DCTERMS.title,
    ]
    local_rdf_dir: str = "rdf"
    endpoint_structure: Optional[Tuple[str, ...]] = ("catalogs", "collections", "items")
    system_endpoints: Optional[List[URIRef]] = [
        EP["system/profile-listing"],
        EP["system/profile-object"],
    ]

    # @root_validator()
    # def check_endpoint_enabled(cls, values):
    #     if not values.get("sparql_endpoint"):
    #         raise ValueError(
    #             'A SPARQL endpoint must be specified using the "SPARQL_ENDPOINT" environment variable'
    #         )
    #     return values
    #
    # @root_validator()
    # def get_version(cls, values):
    #     version = environ.get("PREZ_VERSION")
    #     values["prez_version"] = version
    #
    #     if version is None or version == "":
    #         values["prez_version"] = toml.load(
    #             Path(Path(__file__).parent.parent) / "pyproject.toml"
    #         )["tool"]["poetry"]["version"]
    #
    #     return values


settings = Settings()
