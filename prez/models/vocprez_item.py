from pydantic import BaseModel, root_validator

from prez.services.spaceprez_service import *


class VocabItem(BaseModel):
    uri: Optional[URIRef] = None
    id: Optional[str] = None
    general_class: Optional[URIRef] = None
    scheme_id: Optional[str] = None
    collection_id: Optional[str] = None
    concept_id: Optional[str] = None
    url: Optional[str] = None

    @root_validator
    def populate(cls, values):
        url = values.get("url")
        uri = values.get("uri")
        url_parts = url.split("/")
        if len(url_parts) == 4:
            values["general_class"] = SKOS.Concept
            id = values.get("concept_id")
        elif url_parts[1] == "collection":
            values["general_class"] = SKOS.Collection
            id = values.get("collection_id")
        elif url_parts[1] == "scheme":
            values["general_class"] = SKOS.ConceptScheme
            id = values.get("scheme_id")
        elif url_parts[1] == "vocab":
            values["general_class"] = SKOS.ConceptScheme
            id = values.get("scheme_id")
        assert id or uri, "Either an id or uri must be provided"
        if id:  # get the URI
            q = f"""
                PREFIX dcterms: <{DCTERMS}>
                PREFIX xsd: <{XSD}>

                SELECT ?uri {{
                    ?uri dcterms:identifier "{id}"^^xsd:token ;
                }}
                """
            r = sparql_query_non_async(q, "VocPrez")
            if r[0]:
                # set the uri of the item
                uri = r[1][0].get("uri")["value"]
                if uri:
                    values["uri"] = uri
        # TODO figure out if id is actually required anywhere
        # else:  # uri provided, get the ID
        #     q = f"""
        #         PREFIX dcterms: <{DCTERMS}>
        #
        #         SELECT ?id {{
        #             <{uri}> dcterms:identifier ?id ;
        #         }}
        #         """
        #     r = sparql_query_non_async(q, "VocPrez")
        #     if r[0]:
        #         # set the uri of the item
        #         scheme_id = r[1][0].get("id")
        #         if scheme_id:
        #             values["id"] = id
        return values
