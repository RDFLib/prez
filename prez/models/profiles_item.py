from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, PROF, Namespace

from prez.cache import profiles_graph_cache

PREZ = Namespace("https://prez.dev/")


class ProfileItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]] = frozenset([PROF.Profile])
    id: Optional[str] = None
    link_constructor: str = "/profiles"

    # general_class: Optional[URIRef] = None
    # url_path: Optional[str] = None
    selected_class: Optional[URIRef] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        uri = values.get("uri")
        id = values.get("id")
        assert uri or id
        if id:  # get the URI
            q = f"""
                PREFIX dcterms: <http://purl.org/dc/terms/>
                PREFIX prof: <http://www.w3.org/ns/dx/prof/>
                PREFIX prez: <{PREZ}>


                SELECT ?uri {{
                    ?uri dcterms:identifier "{id}"^^prez:slug ;
                        a prof:Profile .
                }}
                """
            r = profiles_graph_cache.query(q)
            if len(r) > 0:
                # set the uri of the item
                uri = r.bindings[0]["uri"]
                if uri:
                    values["uri"] = uri
        else:  # uri provided, get the ID
            q = f"""SELECT ?class {{ <{uri}> a ?class }}"""
            r = profiles_graph_cache.query(q)
            if len(r.bindings) > 0:
                values["classes"] = frozenset(
                    [prof.get("class") for prof in r.bindings]
                )
        return values
