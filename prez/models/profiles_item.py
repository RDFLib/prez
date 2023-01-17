from typing import Optional
from typing import Set


from pydantic import BaseModel, root_validator
from rdflib import URIRef, SKOS, DCTERMS, XSD, PROF

from prez.cache import profiles_graph_cache

from prez.services.sparql_utils import sparql_query_non_async


class ProfileItem(BaseModel):
    uri: Optional[URIRef] = None
    # classes: Optional[Set[URIRef]]
    id: Optional[str] = None
    link_constructor: str = "/profiles"
    # general_class: Optional[URIRef] = None
    # url_path: Optional[str] = None
    # selected_class: Optional[URIRef] = None

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

                SELECT ?uri {{
                    ?uri dcterms:identifier "{id}" ;
                        a prof:Profile .
                }}
                """
            r = profiles_graph_cache.query(q)
            if r[0]:
                # set the uri of the item
                uri = r[1][0].get("uri")["value"]
                if uri:
                    values["uri"] = uri
        else:  # uri provided, get the ID
            q = f"""SELECT ?class {{ <{uri}> dcterms:identifier ?id }}"""
            r = profiles_graph_cache.query(q)
            if r[0]:
                # set the uri of the item
                id = r[1][0].get("id")["value"]
                if id:
                    values["id"] = id
        return values
