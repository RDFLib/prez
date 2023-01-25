from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef
from rdflib.namespace import DCTERMS, XSD, DCAT, Namespace

from prez.services.sparql_utils import sparql_query_non_async

PREZ = Namespace("https://prez.dev/")


class CatalogItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]]
    id: Optional[str] = None
    general_class: Optional[URIRef] = None
    catalog_id: Optional[str] = None
    resource_id: Optional[str] = None
    url_path: Optional[str] = None
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        uri = values.get("uri")
        id = values.get("id")
        url_parts = url_path.split("/")
        if len(url_parts) == 4:
            values["general_class"] = DCAT.Catalog
            id = values.get("catalog_id")
            values["link_constructor"] = f"/c/catalogs/{id}"
        elif len(url_parts) == 5:
            values["general_class"] = DCAT.Resource
            id = values.get("resource_id")

        assert id or uri, "Either an id or uri must be provided"
        if id:  # get the URI
            q = f"""
                PREFIX dcterms: <{DCTERMS}>
                PREFIX prez: <{PREZ}>
                PREFIX xsd: <{XSD}>

                SELECT ?uri ?class {{
                    ?uri dcterms:identifier "{id}"^^prez:slug ;
                        a ?class .
                }}
                """
            r = sparql_query_non_async(q, "CatPrez")
            if r[0]:
                # set the uri of the item
                uri = r[1][0].get("uri")["value"]
                if uri:
                    values["uri"] = uri
                values["classes"] = frozenset([c["class"]["value"] for c in r[1]])
        else:  # uri provided, get the ID
            q = f"""SELECT ?class {{ <{uri}> a ?class }}"""
            r = sparql_query_non_async(q, "CatPrez")
            if r[0] and r[1]:
                # set the uri of the item
                values["classes"] = frozenset([c["class"]["value"] for c in r[1]])
            else:
                raise ValueError(
                    f"Could not find a class for {uri}, or URI does not exist in CatPrez"
                )
        return values
