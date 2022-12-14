from typing import Optional

from pydantic import (
    BaseSettings,
    root_validator,
)
from rdflib import DCAT, SKOS
from rdflib.namespace import GEO


class Settings(BaseSettings):
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
    generate_context: bool = True
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
    prez_desc: Optional[str] = "A web framework API for delivering Linked Data. It provides read-only access to " \
                               "Knowledge Graph data which can be subset according to information profiles."
    prez_version: str = "3.0.0"

    @root_validator()
    def set_system_uri(cls, values):
        if not values.get("system_uri"):
            values[
                "system_uri"
            ] = f"{values['protocol']}://{values['host']}:{values['port']}"
        return values

    @root_validator()
    def check_endpoints(cls, values):
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

    @root_validator()
    def populate_top_level_classes(cls, values):
        top_level_classes = {
            "SpacePrez": [DCAT.Dataset],
            "VocPrez": [SKOS.ConceptScheme, SKOS.Collection],
            "CatPrez": [DCAT.Catalog],
        }
        values["top_level_classes"] = {}
        for prez in values["enabled_prezs"]:
            values["top_level_classes"][prez] = top_level_classes[prez]
        return values

    @root_validator()
    def populate_collection_classes(cls, values):
        additional_classes = {
            "SpacePrez": [GEO.FeatureCollection],
            "VocPrez": [],
            "CatPrez": [DCAT.Resource],
        }
        values["collection_classes"] = {}
        for prez in values["enabled_prezs"]:
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
        }
        values["general_classes"] = {}
        for prez in values["enabled_prezs"]:
            values["general_classes"][prez] = (
                values["collection_classes"].get(prez) + additional_classes[prez]
            )
        return values

    @root_validator()
    def set_sparql_update_endpoints(cls, values):
        cp_sparql = values.get("catprez_sparql_endpoint")
        if cp_sparql is not None:
            cp_update = values.get("catprez_update_endpoint")
            if cp_update is None:
                values["catprez_update_endpoint"] = cp_sparql

        sp_sparql = values.get("spaceprez_sparql_endpoint")
        if sp_sparql is not None:
            sp_update = values.get("spaceprez_update_endpoint")
            if sp_update is None:
                values["spaceprez_update_endpoint"] = sp_sparql

        vp_sparql = values.get("vocprez_sparql_endpoint")
        if vp_sparql is not None:
            vp_update = values.get("vocprez_update_endpoint")
            if vp_update is None:
                values["vocprez_update_endpoint"] = vp_sparql

        return values
