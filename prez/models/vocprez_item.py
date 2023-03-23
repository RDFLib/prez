from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, SKOS

from prez.sparql.methods import sparql_query_non_async


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
        id = values.get("id")
        url_parts = url_path.split("/")
        if url_path == "/v":
            return values
        elif url_path == "/object":
            pass
        elif len(url_parts) == 3:
            id = None  # /v/profiles
        elif len(url_parts) == 5:
            values["general_class"] = SKOS.Concept
            id = values.get("concept_id")
            scheme_id = values.get("scheme_id")
            collection_id = values.get("collection_id")
            if scheme_id:
                values["link_constructor"] = f"/v/vocab/{scheme_id}"
            elif collection_id:
                values["link_constructor"] = f"/v/collection/{collection_id}"
        elif url_parts[2] == "collection":
            values["general_class"] = SKOS.Collection
            id = values.get("collection_id")
            # TODO probably requires a /object?uri=xyz as the members of a collection can be Concepts or ConceptSchemes
            values["link_constructor"] = f"/v/collection/{id}"
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
                PREFIX dcterms: <http://purl.org/dc/terms/>
                PREFIX prez: <https://prez.dev/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

                SELECT ?uri ?class {{
                    ?uri dcterms:identifier "{id}"^^prez:slug ;
                        a ?class .
                    ?class rdfs:subClassOf* <{values["general_class"]}> .
                }}
                """
            r = sparql_query_non_async(q, "VocPrez")
            if r[0]:
                # set the uri of the item
                uri = r[1][0].get("uri")["value"]
                if uri:
                    values["uri"] = uri
                values["classes"] = frozenset([c["class"]["value"] for c in r[1]])
                return values
            else:
                raise ValueError(f"Could not find an ID for {uri} in VocPrez")
        else:  # uri provided, get the ID
            q = f"""SELECT ?class {{ <{uri}> a ?class }}"""
            r = sparql_query_non_async(q, "VocPrez")
            if r[0] and r[1]:
                # set the uri of the item
                values["classes"] = frozenset([c["class"]["value"] for c in r[1]])
                return values
            else:
                raise ValueError(
                    f"Could not find a class for {uri}, or URI does not exist in VocPrez"
                )
