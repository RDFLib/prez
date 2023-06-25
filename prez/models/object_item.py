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

        # get_parents_query =
        # object_query =

        # values
        #
        # assert uri or id
        # if id:
        #     values["uri"] = get_uri_for_curie_id(id)
        # elif uri:
        #     values["id"] = get_curie_id_for_uri(uri)
        # q = f"""SELECT ?class {{ <{values["uri"]}> a ?class }}"""
        # r = profiles_graph_cache.query(q)
        # if len(r.bindings) > 0:
        #     values["classes"] = frozenset([prof.get("class") for prof in r.bindings])
        # return values

    # get classes from remote endpoint
    # get endpoints which deliver classes & endpoint templates & parent relations for endpoints (from local prez graph)
    # in parallel:
    #   get parent uris from remote endpoint
    #   get object information using open profile from remote endpoint
    # construct the system links using the parent uris from the remote endpoint.
    # merge the response with the system links
