from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, SKOS

from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri
from prez.services.model_methods import get_classes
from prez.sparql.methods import sparql_query_non_async


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

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        uri = values.get("uri")
        curie_id = values.get("curie_id")
        url_parts = url_path.split("/")
        if url_path == "/v":
            return values
        elif url_path == "/object":
            pass
        elif len(url_parts) == 3:
            curie_id = None  # /v/profiles
        elif len(url_parts) == 5:
            values["general_class"] = SKOS.Concept
            curie_id = values.get("concept_curie")
            scheme_curie = values.get("scheme_curie")
            collection_curie = values.get("collection_curie")
            if scheme_curie:
                values["link_constructor"] = f"/v/vocab/{scheme_curie}"
            elif collection_curie:
                values["link_constructor"] = f"/v/collection/{collection_curie}"
        elif url_parts[2] == "collection":
            values["general_class"] = SKOS.Collection
            curie_id = values.get("collection_curie")
            # TODO probably requires a /object?uri=xyz as the members of a collection can be Concepts or ConceptSchemes
            values["link_constructor"] = f"/v/collection/{curie_id}"
        elif url_parts[2] == "scheme":
            values["general_class"] = SKOS.ConceptScheme
            curie_id = values.get("scheme_curie")
            values["link_constructor"] = f"/v/scheme/{curie_id}"
        elif url_parts[2] == "vocab":
            values["general_class"] = SKOS.ConceptScheme
            curie_id = values.get("scheme_curie")
            values["link_constructor"] = f"/v/vocab/{curie_id}"
        assert curie_id or uri, "Either an curie_id or uri must be provided"
        if curie_id:  # get the URI
            values["uri"] = get_uri_for_curie_id(curie_id)
        else:  # uri provided, get the curie_id
            values["curie_id"] = get_curie_id_for_uri(uri)
        values["classes"] = get_classes(values["uri"], "VocPrez")
        return values
