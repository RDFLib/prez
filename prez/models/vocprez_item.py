from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, SKOS, DCTERMS, XSD

from prez.services.sparql_utils import sparql_query_non_async


class VocabItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]]
    id: Optional[str] = None
    general_class: Optional[URIRef] = None
    scheme_id: Optional[str] = None
    collection_id: Optional[str] = None
    concept_id: Optional[str] = None
    url_path: Optional[str] = None
    selected_class: Optional[URIRef] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        uri = values.get("uri")
        url_parts = url_path.split("/")
        if len(url_parts) == 5:
            values["general_class"] = SKOS.Concept
            id = values.get("concept_id")
            scheme_id = values.get("scheme_id")
            values["link_constructor"] = f"/v/vocab/{scheme_id}"
        elif url_parts[2] == "collection":
            values["general_class"] = SKOS.Collection
            id = values.get("collection_id")
            # TODO probably requires a /object?uri=xyz as the members of a collection can be Concepts or ConceptSchemes
            values["link_constructor"] = f"/v/vocab/{id}"
        elif url_parts[2] == "scheme":
            values["general_class"] = SKOS.ConceptScheme
            id = values.get("scheme_id")
            values["link_constructor"] = f"/v/scheme/{id}"
        elif url_parts[2] == "vocab":
            values["general_class"] = SKOS.ConceptScheme
            id = values.get("scheme_id")
            values["link_constructor"] = f"/v/vocab/{id}"
        assert id or uri, "Either an id or uri must be provided"
        if id:  # get the URI
            q = f"""
                PREFIX dcterms: <{DCTERMS}>
                PREFIX xsd: <{XSD}>

                SELECT ?uri ?class {{
                    ?uri dcterms:identifier "{id}"^^xsd:token ;
                        a ?class .
                }}
                """
            r = sparql_query_non_async(q, "VocPrez")
            if r[0]:
                # set the uri of the item
                uri = r[1][0].get("uri")["value"]
                if uri:
                    values["uri"] = uri
                values["classes"] = frozenset([c["class"]["value"] for c in r[1]])
        else:  # uri provided, get the ID
            q = f"""SELECT ?class {{ <{uri}> a ?class }}"""
            r = sparql_query_non_async(q, "VocPrez")
            if r[0]:
                # set the uri of the item
                values["classes"] = frozenset([c["class"]["value"] for c in r[1]])
        return values
