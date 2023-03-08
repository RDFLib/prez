from string import Template

from pydantic import BaseModel
from rdflib import URIRef, Namespace, Literal

PREZ = Namespace("https://prez.dev/")


class SearchMethod(BaseModel):
    uri: URIRef = None
    identifier: Literal = None
    title: Literal = None
    template_query: Template = None

    def __hash__(self):
        return hash(self.uri)
