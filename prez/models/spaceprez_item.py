from typing import Optional
from typing import Set

from pydantic import BaseConfig
from pydantic import BaseModel, root_validator
from rdflib import Namespace, URIRef
from rdflib.namespace import DCAT, GEO

from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.model_methods import get_classes
from prez.sparql.methods import sparql_query_non_async

PREZ = Namespace("https://prez.dev/")

BaseConfig.arbitrary_types_allowed = True


class SpatialItem(BaseModel):
    id: Optional[str]
    uri: Optional[URIRef]
    url_path: Optional[str]
    general_class: Optional[URIRef]
    feature_curie: Optional[str]
    collection_curie: Optional[str]
    dataset_curie: Optional[str]
    parent_curie: Optional[str]
    parent_uri: Optional[URIRef]
    classes: Optional[Set[URIRef]]
    link_constructor: Optional[str]
    selected_class: Optional[URIRef] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        dataset_curie = values.get("dataset_curie")
        collection_curie = values.get("collection_curie")
        feature_curie = values.get("feature_curie")

        if feature_curie:
            values["id"] = feature_curie
            values["uri"] = get_uri_for_curie_id(feature_curie)
            values["general_class"] = GEO.Feature
            values["parent_uri"] = get_uri_for_curie_id(collection_curie)
            values["parent_curie"] = collection_curie
        elif collection_curie:
            values["id"] = collection_curie
            values["uri"] = get_uri_for_curie_id(collection_curie)
            values["general_class"] = GEO.FeatureCollection
            values["parent_uri"] = get_uri_for_curie_id(dataset_curie)
            values["parent_curie"] = dataset_curie
            values[
                "link_constructor"
            ] = f"/s/datasets/{dataset_curie}/collections/{collection_curie}/items"
        elif dataset_curie:
            values["id"] = dataset_curie
            values["uri"] = get_uri_for_curie_id(dataset_curie)
            values["general_class"] = DCAT.Dataset
            values["link_constructor"] = f"/s/datasets/{dataset_curie}/collections"
        values["classes"] = get_classes(values["uri"], "SpacePrez")
        return values