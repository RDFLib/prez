from pathlib import Path
from typing import Optional

import toml
from httpx import AsyncClient
from pydantic import BaseSettings, root_validator
from rdflib import URIRef
from rdflib.namespace import GEO, DCAT, SKOS, PROF

from prez.reference_data.prez_ns import PREZ


class SPARQLAsyncClient:
    def __init__(self, auth, base_url):
        self.client = AsyncClient(auth=auth, base_url=base_url, timeout=9999)

    async def close(self):
        await self.client.aclose()


class Settings(BaseSettings):
    """
    spaceprez_sparql_endpoint: Read-only SPARQL endpoint for SpacePrez
    spaceprez_sparql_update: Read/write SPARQL endpoint for SpacePrez
    catprez_sparql_endpoint: Read-only SPARQL endpoint for CatPrez
    catprez_sparql_update: Read/write SPARQL endpoint for CatPrez
    vocprez_sparql_endpoint: Read-only SPARQL endpoint for VocPrez
    vocprez_sparql_update: Read/write SPARQL endpoint for VocPrez
    spaceprez_sparql_username: A username for the SpacePrez SPARQL endpoints, if required by the RDF DB
    catprez_sparql_username: A username for the CatPrez SPARQL endpoints, if required by the RDF DB
    vocprez_sparql_username: A username for the VocPrez SPARQL endpoints, if required by the RDF DB
    spaceprez_sparql_password:  A password for the SpacePrez SPARQL endpoints, if required by the RDF DB
    catprez_sparql_password: A password for the CatPrez SPARQL endpoints, if required by the RDF DB
    vocprez_sparql_password: A password for the VocPrez SPARQL endpoints, if required by the RDF DB
    protocol: The protocol used to deliver Prez. Usually 'http', could be 'https'.
    host: Prez' host domain name. Usually 'localhost' but could be anything
    port: The port Prez is made accissible on. Default is 8000, could be 80 or anything else that your system has permission to use
    system_uri: Documentation property. An IRI for the Prez system as a whole. This value appears in the landing page RDF delivered by Prez ('/')
    top_level_classes:
    collection_classes:
    general_classes:
    enabled_prezs:
    generate_support_graphs:
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

    spaceprez_sparql_endpoint: Optional[str]
    spaceprez_sparql_update: Optional[str]
    catprez_sparql_endpoint: Optional[str]
    catprez_sparql_update: Optional[str]
    vocprez_sparql_endpoint: Optional[str]
    vocprez_sparql_update: Optional[str]
    spaceprez_sparql_username: Optional[str]
    catprez_sparql_username: Optional[str]
    vocprez_sparql_username: Optional[str]
    spaceprez_sparql_password: Optional[str]
    catprez_sparql_password: Optional[str]
    vocprez_sparql_password: Optional[str]
    protocol: str = "http"
    host: str = "localhost"
    port: int = 8000
    system_uri: Optional[str]
    top_level_classes: Optional[dict]
    collection_classes: Optional[dict]
    general_classes: Optional[dict]
    enabled_prezs: Optional[list]
    generate_support_graphs: bool = True
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
    def set_enabled_prezs(cls, values):
        sp_ep = values.get("spaceprez_sparql_endpoint")
        cp_ep = values.get("catprez_sparql_endpoint")
        vp_ep = values.get("vocprez_sparql_endpoint")
        values["enabled_prezs"] = [
            name
            for name, ep in zip(
                ["SpacePrez", "CatPrez", "VocPrez"], [sp_ep, cp_ep, vp_ep]
            )
            if ep
        ]
        if len(values["enabled_prezs"]) == 0:
            raise ValueError(
                "one or more of spaceprez, vocprez, or catprez SPARQL endpoints are required for Prez to start."
            )
        return values

    @root_validator()
    def populate_top_level_classes(cls, values):
        top_level_classes = {
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
        values["top_level_classes"] = {}
        for prez in values["enabled_prezs"] + ["Profiles"]:
            values["top_level_classes"][prez] = top_level_classes[prez]
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
        for prez in values["enabled_prezs"] + ["Profiles"]:
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
        for prez in values["enabled_prezs"] + ["Profiles"]:
            values["general_classes"][prez] = (
                values["collection_classes"].get(prez) + additional_classes[prez]
            )
        return values

    @root_validator()
    def set_sparql_update_endpoints(cls, values):
        cp_sparql = values.get("catprez_sparql_endpoint")
        if cp_sparql is not None:
            cp_update = values.get("catprez_sparql_update")
            if cp_update is None:
                values["catprez_sparql_update"] = cp_sparql
        # protect future calls to values["catprez_sparql_update"] even when no values
        if values.get("catprez_sparql_update") is None:
            values["catprez_sparql_update"] = None

        sp_sparql = values.get("spaceprez_sparql_endpoint")
        if sp_sparql is not None:
            sp_update = values.get("spaceprez_sparql_update")
            if sp_update is None:
                values["spaceprez_sparql_update"] = sp_sparql
        if values.get("spaceprez_sparql_update") is None:
            values["spaceprez_sparql_update"] = None

        vp_sparql = values.get("vocprez_sparql_endpoint")
        if vp_sparql is not None:
            vp_update = values.get("vocprez_sparql_update")
            if vp_update is None:
                values["vocprez_sparql_update"] = vp_sparql
        if values.get("vocprez_sparql_update") is None:
            values["vocprez_sparql_update"] = None

        return values

    @root_validator()
    def populate_sparql_creds(cls, values):
        values["sparql_creds"] = {
            "CatPrez": {},
            "VocPrez": {},
            "SpacePrez": {},
        }
        for prez in values["enabled_prezs"]:
            for attr in ["endpoint", "username", "password", "update"]:
                key = f"{prez.lower()}_sparql_{attr}"
                value = values[key]
                if value:
                    values["sparql_creds"][prez][attr] = value
        return values


settings = Settings()
