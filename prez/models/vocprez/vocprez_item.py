from fastapi import APIRouter
from pydantic import BaseModel, root_validator

from prez.services.spaceprez_service import *

PREZ = Namespace("https://surroundaustralia.com/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


class VocPrezItem(BaseModel):
    uri: Optional[URIRef] = None
    id: Optional[str] = None
    general_class: Optional[URIRef] = None
    scheme_id: Optional[str] = None
    collection_id: Optional[str] = None
    url: Optional[str] = None

    @root_validator
    def populate(cls, values):
        url = values.get("url")
        id = values.get("scheme_id", values.get("collection_id"))
        uri = values.get("uri")
        assert id or uri, "Either an id or uri must be provided"
        url_parts = url.split("/")
        if url_parts[1] == "collection":
            values["general_class"] = SKOS.Collection
        elif url_parts[1] == "scheme":
            values["general_class"] = SKOS.ConceptScheme
        elif url_parts[1] == "vocab":
            values["general_class"] = SKOS.ConceptScheme
        if id:  # get the URI
            q = f"""
                PREFIX dcterms: <{DCTERMS}>
                PREFIX xsd: <{XSD}>

                SELECT ?cs_uri {{
                    ?cs_uri dcterms:identifier "{id}"^^xsd:token ;
                }}
                """
            r = sparql_query_non_async(q, "VocPrez")
            if r[0]:
                # set the uri of the item
                cs_uri = r[1][0].get("cs_uri")["value"]
                if cs_uri:
                    values["uri"] = cs_uri
        else:  # uri provided, get the scheme ID
            q = f"""
                PREFIX dcterms: <{DCTERMS}>

                SELECT ?id {{
                    <{uri}> dcterms:identifier ?id ;
                }}
                """
            r = sparql_query_non_async(q, "VocPrez")
            if r[0]:
                # set the uri of the item
                scheme_id = r[1][0].get("id")
                if scheme_id:
                    values["id"] = id
        return values
