from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace
from rdflib.namespace import URIRef, SKOS

PREZ = Namespace("https://kurrawong.net/prez/")


class VocPrezMembers(BaseModel):
    url_path: str
    uri: Optional[URIRef] = None
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        if url_path == "/collection":
            values["general_class"] = SKOS.Collection
            values["link_constructor"] = "/collection/"
            values["classes"] = frozenset([PREZ.VocPrezCollectionList])
        elif url_path == "/scheme":
            values["general_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/scheme/"
            values["classes"] = frozenset([PREZ.SchemesList])
        elif url_path == "/vocab":
            values["general_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/vocab/"
            values["classes"] = frozenset([PREZ.SchemesList])
        return values
