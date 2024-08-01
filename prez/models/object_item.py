from typing import Optional, FrozenSet

from pydantic import BaseModel
from rdflib import URIRef, PROF


class ObjectItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[FrozenSet[URIRef]] = frozenset([PROF.Profile])
    selected_class: Optional[URIRef] = None
    profile: Optional[URIRef] = None
    top_level_listing: Optional[bool] = False

    def __hash__(self):
        return hash(self.uri)
