from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace, DCAT, XSD, RDFS, DCTERMS
from rdflib.namespace import URIRef, GEO

from prez.services.sparql_utils import sparql_query_non_async

PREZ = Namespace("https://prez.dev/")


class SpatialMembers(BaseModel):
    url_path: str
    uri: Optional[URIRef] = None
    dataset_id: Optional[URIRef]
    collection_id: Optional[URIRef]
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    selected_class: Optional[URIRef] = None
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        n_url_path_components = len(values.get("url_path").split("/"))
        if n_url_path_components == 3:  # /s/datasets
            values["general_class"] = DCAT.Dataset
            values["link_constructor"] = "/s/datasets"
            values["classes"] = frozenset([PREZ.DatasetList])
        elif n_url_path_components == 5:  # /s/datasets/{dataset_id}/collections
            dataset_id = values.get("dataset_id")
            values["general_class"] = GEO.FeatureCollection
            values["link_constructor"] = f"/s/datasets/{dataset_id}/collections"
            values["classes"] = frozenset([PREZ.FeatureCollectionList])
            _, values["uri"] = get_uri(dataset_id)
        elif (
            n_url_path_components == 7
        ):  # /s/datasets/{dataset_id}/collections/{collection_id}/items
            dataset_id = values.get("dataset_id")
            collection_id = values.get("collection_id")
            values["general_class"] = GEO.Feature
            values[
                "link_constructor"
            ] = f"/s/datasets/{dataset_id}/collections/{collection_id}/items"
            values["classes"] = frozenset([PREZ.FeatureList])
            values["uri"], _ = get_uri(dataset_id, collection_id)
        return values


def get_uri(dataset_id, collection_id=None):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        PREFIX xsd: <{XSD}>

        SELECT ?fc ?d {{
            ?d dcterms:identifier "{dataset_id}"^^xsd:token ;
                    a dcat:Dataset .
            {f'''?fc dcterms:identifier "{collection_id}"^^xsd:token ;
                    a geo:FeatureCollection .
                ?d rdfs:member ?fc .''' if collection_id else ""}
                }}
        """
    r = sparql_query_non_async(q, "SpacePrez")
    if r[0]:
        # set the uri of the item
        fc = r[1][0].get("fc")
        d = r[1][0].get("d")
        fc = URIRef(fc["value"]) if fc else None
        d = URIRef(d["value"]) if d else None
    return fc, d
