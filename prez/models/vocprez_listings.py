from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace
from rdflib.namespace import URIRef, SKOS

PREZ = Namespace("https://prez.dev/")


class VocabMembers(BaseModel):
    url_path: str
    uri: Optional[URIRef] = None
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        if url_path == "/v/collection":
            values["general_class"] = SKOS.Collection
            values["link_constructor"] = "/v/collection"
            values["classes"] = frozenset([PREZ.VocPrezCollectionList])
        elif url_path == "/v/scheme":
            values["general_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/v/scheme"
            values["classes"] = frozenset([PREZ.SchemesList])
        elif url_path == "/v/vocab":
            values["general_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/v/vocab"
            values["classes"] = frozenset([PREZ.SchemesList])
        return values
