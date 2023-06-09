from string import Template

from pydantic import BaseModel
from rdflib import URIRef, Namespace, Literal

PREZ = Namespace("https://prez.dev/")


class SearchMethod(BaseModel):
    uri: URIRef = None
    identifier: Literal = None
    title: Literal = None
    template_query: Template = None
    top_level_listing = False
    search_query = True
    selected_class: URIRef = None
    populated_query: str = None
    link_constructor: str = "/object?uri="

    def __hash__(self):
        return hash(self.uri)

    def populate_query(self, term, limit):
        self.populated_query = self.template_query.substitute(
            {"TERM": term, "LIMIT": limit}
        )
