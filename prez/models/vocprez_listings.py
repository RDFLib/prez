from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace
from rdflib.namespace import URIRef, SKOS

PREZ = Namespace("https://prez.dev/")


class VocabMembers(BaseModel):
    url_path: str
    uri: Optional[URIRef] = None
    base_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str]
    top_level_listing: Optional[bool] = True

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        if url_path == "/v/collection":
            values["base_class"] = SKOS.Collection
            values["link_constructor"] = "/v/collection"
            values["classes"] = frozenset([PREZ.VocPrezCollectionList])
        elif url_path == "/v/scheme":
            values["base_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/v/scheme"
            values["classes"] = frozenset([PREZ.SchemesList])
        elif url_path == "/v/vocab":
            values["base_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/v/vocab"
            values["classes"] = frozenset([PREZ.SchemesList])
        return values
