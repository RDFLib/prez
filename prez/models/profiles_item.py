from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, PROF, Namespace

from prez.cache import profiles_graph_cache
from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri
from prez.services.model_methods import get_classes

PREZ = Namespace("https://prez.dev/")


class ProfileItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]] = frozenset([PROF.Profile])
    id: Optional[str] = None
    link_constructor: str = "/profiles"
    label: str = None

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
        if id:
            values["uri"] = get_uri_for_curie_id(id)
        elif uri:
            values["id"] = get_curie_id_for_uri(uri)
        q = f"""SELECT ?class {{ <{values["uri"]}> a ?class }}"""
        r = profiles_graph_cache.query(q)
        if len(r.bindings) > 0:
            values["classes"] = frozenset([prof.get("class") for prof in r.bindings])

        values["label"] = profiles_graph_cache.value(
            URIRef(values["uri"]),
            URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#hasLabelPredicate"),
        )
        return values
