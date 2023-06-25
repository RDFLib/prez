from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, PROF

from prez.models.model_exceptions import ClassNotFoundException
from prez.services.model_methods import get_classes


class ObjectItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]] = frozenset([PROF.Profile])
    selected_class: Optional[URIRef] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        try:
            values["classes"] = get_classes(values["uri"])
        except ClassNotFoundException:
            # TODO return a generic DESCRIBE on the object - we can't use any of prez's profiles/endpoints to render
            # information about the object, but we can provide any RDF we have for it.
            pass
        uri_str = values["uri"]
        values["uri"] = URIRef(uri_str)
        return values
