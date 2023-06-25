from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, SKOS

from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.model_methods import get_classes


class VocabItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]]
    curie_id: Optional[str] = None
    base_class: Optional[URIRef] = None
    scheme_curie: Optional[str] = None
    collection_curie: Optional[str] = None
    concept_curie: Optional[str] = None
    url_path: Optional[str] = None
    endpoint_uri: Optional[str]
    selected_class: Optional[URIRef] = None
    top_level_listing: Optional[bool] = False

    def __hash__(self):
        """
        Required to make object hashable and in turn cacheable
        """
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        concept_curie = values.get("concept_curie")
        scheme_curie = values.get("scheme_curie")
        collection_curie = values.get("collection_curie")
        url_parts = url_path.split("/")
        endpoint_uri = values.get("endpoint_uri")
        values["endpoint_uri"] = URIRef(endpoint_uri)
        if url_path == "/v":
            return values
        elif len(url_parts) == 5:  # concepts
            values["base_class"] = SKOS.Concept
            if scheme_curie:
                values["curie_id"] = concept_curie
                values["link_constructor"] = f"/v/vocab/{scheme_curie}"
            elif collection_curie:
                # TODO: Check if this path is ever reached.
                values["curie_id"] = concept_curie
                values["link_constructor"] = f"/v/collection/{collection_curie}"
        elif url_parts[2] == "collection":  # collections
            values["curie_id"] = values.get("collection_curie")
            values["base_class"] = SKOS.Collection
            values["link_constructor"] = f"/v/collection/{collection_curie}"
        elif url_parts[2] in ["scheme", "vocab"]:  # vocabularies
            values["base_class"] = SKOS.ConceptScheme
            values["curie_id"] = values.get("scheme_curie")
            values["link_constructor"] = f"/v/vocab/{scheme_curie}"

        if not values["uri"]:
            values["uri"] = get_uri_for_curie_id(values["curie_id"])
        values["classes"] = get_classes(values["uri"], values["endpoint_uri"])
        return values
