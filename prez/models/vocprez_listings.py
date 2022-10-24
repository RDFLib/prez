from fastapi import APIRouter
from pydantic import BaseModel, root_validator

from prez.services.spaceprez_service import *

PREZ = Namespace("https://kurrawong.net/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


class VocPrezMembers(BaseModel):
    url: str
    uri: Optional[URIRef] = None
    children_general_class: Optional[URIRef]
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        url = values.get("url")
        if url == "/collection":
            values["children_general_class"] = SKOS.Collection
            values["link_constructor"] = "/collection/"
        elif url == "/scheme":
            values["children_general_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/scheme/"
        elif url == "/vocab":
            values["children_general_class"] = SKOS.ConceptScheme
            values["link_constructor"] = "/vocab/"
        return values
