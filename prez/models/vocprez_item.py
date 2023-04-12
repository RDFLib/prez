from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, SKOS

from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri
from prez.services.model_methods import get_classes


class VocabItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]]
    curie_id: Optional[str] = None
    general_class: Optional[URIRef] = None
    scheme_curie: Optional[str] = None
    collection_curie: Optional[str] = None
    concept_curie: Optional[str] = None
    url_path: Optional[str] = None
    selected_class: Optional[URIRef] = None
    top_level_listing: Optional[bool] = False

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        uri = values.get("uri")
        concept_curie = values.get("concept_curie")
        scheme_curie = values.get("scheme_curie")
        collection_curie = values.get("collection_curie")
        url_parts = url_path.split("/")
        if url_path == "/v":
            return values
        if url_path in ["/object", "/v/object"]:
            values["link_constructor"] = f"/v/object?uri="
        elif len(url_parts) == 5:  # concepts
            values["general_class"] = SKOS.Concept
            if scheme_curie:
                values["curie_id"] = concept_curie
                values["link_constructor"] = f"/v/vocab/{scheme_curie}"
            elif collection_curie:
                values["curie_id"] = concept_curie
                values["link_constructor"] = f"/v/collection/{collection_curie}"
        elif url_parts[2] == "collection":  # collections
            values["curie_id"] = values.get("collection_curie")
            values["general_class"] = SKOS.Collection
            values["link_constructor"] = f"/v/object?uri="
        elif url_parts[2] in ["scheme", "vocab"]:  # vocabularies
            values["general_class"] = SKOS.ConceptScheme
            values["curie_id"] = values.get("scheme_curie")
            values["link_constructor"] = f"/v/scheme/{scheme_curie}"

        if not values["uri"]:
            values["uri"] = get_uri_for_curie_id(values["curie_id"])
        values["classes"] = get_classes(values["uri"], "VocPrez")
        return values
