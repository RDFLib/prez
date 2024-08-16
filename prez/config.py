from os import environ
from pathlib import Path
from typing import Optional, Union, Any, Dict
from typing import Optional, List, Tuple
from typing import Union, Any, Dict

import toml
from pydantic import field_validator
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
    listing_count_limit: The maximum number of items to count for a listing endpoint. Counts greater than this limit will be returned as ">N" where N is the limit.
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
    listing_count_limit: int = 100
    search_count_limit: int = 10
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
    other_predicates: Optional[List[URIRef]] = [SDO.color, REG.status]
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
    prez_contact: Optional[Dict[str, Union[str, Any]]] = None
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

    @field_validator("prez_version")
    @classmethod
    def get_version(cls, v):
        if v:
            return v
        version = environ.get("PREZ_VERSION")
        if version:
            return version

        if version is None or version == "":
            possible_locations = (
                # dir above /prez, this is present in dev environments
                # this is also used by derived projects to override the app version
                Path(__file__).parent.parent,
                # _inside_ /prez module, this is present in wheel builds
                Path(__file__).parent,
            )
            p: Path
            for p in possible_locations:
                if (p / "pyproject.toml").exists():
                    values = toml.load(p / "pyproject.toml")["tool"]["poetry"][
                        "version"
                    ]
                    return values
            else:
                raise RuntimeError(
                    "PREZ_VERSION not set, and cannot find a pyproject.toml to extract the version."
                )


settings = Settings()
