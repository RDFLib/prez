from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import URIRef, Literal, XSD

from prez.cache import endpoints_graph_cache
from prez.reference_data.prez_ns import ONT


class ListingModel(BaseModel):
    uri: Optional[
        URIRef
    ] = None  # this is the URI of the focus object (if listing by membership)
    classes: Optional[FrozenSet[URIRef]] = None
    endpoint_uri: Optional[URIRef] = None
    selected_class: Optional[FrozenSet[URIRef]] = None
    profile: Optional[URIRef] = None
    top_level_listing: Optional[bool] = False

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
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
            tll_text = endpoints_graph_cache.value(endpoint_uri, ONT.isTopLevelEndpoint)
            if tll_text == Literal("true", datatype=XSD.boolean):
                values["top_level_listing"] = True
            else:
                values["top_level_listing"] = False
        return values
