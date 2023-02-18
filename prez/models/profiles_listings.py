from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace
from rdflib.namespace import URIRef, PROF

PREZ = Namespace("https://prez.dev/")


class ProfilesMembers(BaseModel):
    url_path: str
    uri: Optional[URIRef] = None
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]] = frozenset([PREZ.ProfilesList])
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        values["general_class"] = PROF.Profile
        values["link_constructor"] = "/profiles"
        # values["uri"] = PREZ.ProfilesList

        start_of_path = values.get("url_path")[:3]
        pathmap = {
            "/v/": PREZ.VocPrezProfileList,
            "/c/": PREZ.CatPrezProfileList,
            "/s/": PREZ.SpacePrezProfileList,
        }
        values["uri"] = pathmap.get(start_of_path, PREZ.ProfilesList)
        values["classes"] = frozenset([values["uri"]])
        return values
