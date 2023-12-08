from typing import Optional, FrozenSet

from pydantic import BaseModel
from rdflib import Namespace
from rdflib.namespace import URIRef

PREZ = Namespace("https://prez.dev/")


class ProfilesMembers(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    url_path: str
    uri: Optional[URIRef] = None
    base_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]] = frozenset([PREZ.ProfilesList])
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str]
    top_level_listing: Optional[bool] = True
