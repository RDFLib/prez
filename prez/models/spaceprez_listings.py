from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace, DCAT, XSD, RDFS, DCTERMS
from rdflib.namespace import URIRef, GEO

from prez.services.curie_functions import get_uri_for_curie_id
from prez.sparql.methods import sparql_query_non_async
from prez.reference_data.prez_ns import PREZ


class SpatialMembers(BaseModel):
    uri: Optional[URIRef] = None
    url_path: str
    parent_uri: Optional[URIRef] = None
    dataset_curie: Optional[URIRef]
    collection_curie: Optional[URIRef]
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    selected_class: Optional[FrozenSet[URIRef]] = None
    top_level_listing: Optional[bool] = False
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        url_path = values["url_path"]
        if url_path.endswith("/datasets"):  # /s/datasets
            values["general_class"] = DCAT.Dataset
            values["link_constructor"] = "/s/datasets"
            values["classes"] = frozenset([PREZ.DatasetList])
            # graph
            values["top_level_listing"] = True  # used in the construct query
            values["uri"] = None
        elif url_path.endswith("/collections"):  # /s/datasets/{dataset_curie}/collections
            dataset_curie = values.get("dataset_curie")
            values["general_class"] = GEO.FeatureCollection
            values["link_constructor"] = f"/s/datasets/{dataset_curie}/collections"
            values["classes"] = frozenset([PREZ.FeatureCollectionList])
            values["uri"] = get_uri_for_curie_id(dataset_curie)
        elif url_path.endswith("/items"):  # /s/datasets/{dataset_curie}/collections/{collection_curie}/items
            dataset_curie = values.get("dataset_curie")
            collection_curie = values.get("collection_curie")
            values["general_class"] = GEO.Feature
            values[
                "link_constructor"
            ] = f"/s/datasets/{dataset_curie}/collections/{collection_curie}/items"
            values["classes"] = frozenset([PREZ.FeatureList])
            values["uri"] = get_uri_for_curie_id(collection_curie)
        return values
