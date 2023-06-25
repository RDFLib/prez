from typing import Optional
from typing import Set

from pydantic import BaseConfig
from pydantic import BaseModel, root_validator
from rdflib import URIRef
from rdflib.namespace import DCAT, GEO

from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.model_methods import get_classes

BaseConfig.arbitrary_types_allowed = True


class SpatialItem(BaseModel):
    id: Optional[str]
    uri: Optional[URIRef]
    url_path: Optional[str]
    endpoint_uri: Optional[str]
    base_class: Optional[URIRef]
    feature_curie: Optional[str]
    collection_curie: Optional[str]
    dataset_curie: Optional[str]
    classes: Optional[Set[URIRef]]
    link_constructor: Optional[str]
    selected_class: Optional[URIRef] = None
    top_level_listing: Optional[bool] = False

    def __hash__(self):
        """
        Required to make object hashable and in turn cacheable
        """
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        dataset_curie = values.get("dataset_curie")
        collection_curie = values.get("collection_curie")
        feature_curie = values.get("feature_curie")
        endpoint_uri = values.get("endpoint_uri")
        values["endpoint_uri"] = URIRef(endpoint_uri)
        if feature_curie:
            values["id"] = feature_curie
            values["uri"] = get_uri_for_curie_id(feature_curie)
            values["base_class"] = GEO.Feature
        elif collection_curie:
            values["id"] = collection_curie
            values["uri"] = get_uri_for_curie_id(collection_curie)
            values["base_class"] = GEO.FeatureCollection
            values[
                "link_constructor"
            ] = f"/s/datasets/{dataset_curie}/collections/{collection_curie}/items"
        elif dataset_curie:
            values["id"] = dataset_curie
            values["uri"] = get_uri_for_curie_id(dataset_curie)
            values["base_class"] = DCAT.Dataset
            values["link_constructor"] = f"/s/datasets/{dataset_curie}/collections"
        values["classes"] = get_classes(values["uri"], values["endpoint_uri"])
        return values
