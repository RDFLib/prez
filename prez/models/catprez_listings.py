from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace, URIRef
from rdflib.namespace import DCAT

PREZ = Namespace("https://kurrawong.net/prez/")


class CatalogMembers(BaseModel):
    url_path: str
    uri: Optional[URIRef] = None
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        if url_path == "/c/catalogs":
            values["general_class"] = DCAT.Catalog
            values["link_constructor"] = "/c/catalogs"
            values["classes"] = frozenset([PREZ.CatalogList])
        return values
