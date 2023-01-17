from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace
from rdflib.namespace import URIRef, SKOS, PROF

PREZ = Namespace("https://prez.dev/")


class ProfilesMembers(BaseModel):
    uri: Optional[URIRef] = None
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        values["general_class"] = PROF.Profile
        values["link_constructor"] = "/profiles"
        values["classes"] = frozenset([PREZ.ProfilesList])
        values["uri"] = PREZ.ProfilesList
        return values
