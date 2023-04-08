from typing import Optional
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef
from rdflib.namespace import DCTERMS, XSD, DCAT, Namespace

from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri
from prez.services.model_methods import get_classes
from prez.sparql.methods import sparql_query_non_async

PREZ = Namespace("https://prez.dev/")


class CatalogItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[Set[URIRef]]
    curie_id: Optional[str] = None
    general_class: Optional[URIRef] = None
    catalog_curie: Optional[str] = None
    resource_curie: Optional[str] = None
    url_path: Optional[str] = None
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        url_path = values.get("url_path")
        uri = values.get("uri")
        curie_id = values.get("curie_id")
        url_parts = url_path.split("/")
        if url_path in ["/object", "/c/object"]:
            values["link_constructor"] = f"/c/object?uri="
        if len(url_parts) == 4:
            values["general_class"] = DCAT.Catalog
            curie_id = values.get("catalog_curie")
            values["link_constructor"] = f"/c/catalogs/{curie_id}"
        elif len(url_parts) == 5:
            values["general_class"] = DCAT.Resource
            curie_id = values.get("resource_curie")
        assert curie_id or uri, "Either an curie_id or uri must be provided"
        if curie_id:  # get the URI
            values["uri"] = get_uri_for_curie_id(curie_id)
        else:  # uri provided, get the curie_id
            values["curie_id"] = get_curie_id_for_uri(uri)
        values["classes"] = get_classes(values["uri"], "CatPrez")
        return values
