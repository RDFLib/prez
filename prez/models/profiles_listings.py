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
    top_level_listing: Optional[bool] = True

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        if url_path.startswith("/v/"):
            values["general_class"] = PREZ.VocPrezProfile
            values["link_constructor"] = "/v/profiles"
        elif url_path.startswith("/c/"):
            values["general_class"] = PREZ.CatPrezProfile
            values["link_constructor"] = "/c/profiles"
        elif url_path.startswith("/s/"):
            values["general_class"] = PREZ.SpacePrezProfile
            values["link_constructor"] = "/s/profiles"
        else:
            values["general_class"] = PROF.Profile
            values["link_constructor"] = "/profiles"
        return values
