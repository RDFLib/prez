from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, PROF

from prez.cache import endpoints_graph_cache
from prez.models.model_exceptions import ClassNotFoundException
from prez.reference_data.prez_ns import PREZ, ONT
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.model_methods import get_classes


class ObjectItem(BaseModel):
    uri: Optional[URIRef] = None
    object_curie: Optional[str] = None
    classes: Optional[Set[URIRef]] = frozenset([PROF.Profile])
    selected_class: Optional[URIRef] = None
    profile: Optional[URIRef] = PREZ["profile/open"]
    link_constructor: Optional[str] = None  # TODO remove when no longer being used
    endpoint_uri: Optional[URIRef] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        values["top_level_listing"] = False  # this class is for objects, not listings.
        uri_str = values.get("uri")
        endpoint_uri_str = values.get("endpoint_uri")
        if endpoint_uri_str:
            endpoint_uri = URIRef(endpoint_uri_str)
            values["classes"] = frozenset(
                [
                    klass
                    for klass in endpoints_graph_cache.objects(
                        endpoint_uri, ONT.deliversClasses, None
                    )
                ]
            )
            values["base_class"] = endpoints_graph_cache.value(
                endpoint_uri, ONT.baseClass
            )
        else:
            try:
                values["classes"] = frozenset(
                    tup[1] for tup in get_classes([values["uri"]])
                )
            except ClassNotFoundException:
                # TODO return a generic DESCRIBE on the object - we can't use any of prez's profiles/endpoints to render
                # information about the object, but we can provide any RDF we have for it.
                pass
        if uri_str:
            values["uri"] = URIRef(uri_str)
        else:
            values["uri"] = get_uri_for_curie_id(values["object_curie"])

        return values
