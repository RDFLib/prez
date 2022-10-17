from fastapi import APIRouter
from pydantic import BaseModel, root_validator

from prez.services.spaceprez_service import *

PREZ = Namespace("https://surroundaustralia.com/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


class VocPrezMembers(BaseModel):
    url: str
    general_class: Optional[URIRef]

    @root_validator
    def populate(cls, values):
        url = values.get("url")
        if url == "/collection":
            values["general_class"] = SKOS.Collection
        elif url == "/scheme":
            values["general_class"] = SKOS.ConceptScheme
        elif url == "/vocab":
            values["general_class"] = SKOS.ConceptScheme
        return values
