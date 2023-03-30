from typing import Optional, FrozenSet

from pydantic import BaseModel, root_validator
from rdflib import Namespace, DCAT, XSD, RDFS, DCTERMS
from rdflib.namespace import URIRef, GEO

from prez.services.curie_functions import get_uri_for_curie_id
from prez.sparql.methods import sparql_query_non_async

PREZ = Namespace("https://prez.dev/")


class SpatialMembers(BaseModel):
    url_path: str
    uri: Optional[URIRef] = None
    dataset_curie: Optional[URIRef]
    collection_curie: Optional[URIRef]
    general_class: Optional[URIRef]
    classes: Optional[FrozenSet[URIRef]]
    selected_class: Optional[FrozenSet[URIRef]] = None
    link_constructor: Optional[str]

    @root_validator
    def populate(cls, values):
        n_url_path_components = len(values.get("url_path").split("/"))
        if n_url_path_components == 3:  # /s/datasets
            values["general_class"] = DCAT.Dataset
            values["link_constructor"] = "/s/datasets"
            values["classes"] = frozenset([PREZ.DatasetList])
            values["uri"] = PREZ.DatasetList  # Prez construct which contains (via rdfs:member) all dcat:Datasets in the
            # graph
        elif n_url_path_components == 5:  # /s/datasets/{dataset_curie}/collections
            dataset_curie = values.get("dataset_curie")
            values["general_class"] = GEO.FeatureCollection
            values["link_constructor"] = f"/s/datasets/{dataset_curie}/collections"
            values["classes"] = frozenset([PREZ.FeatureCollectionList])
            values["uri"] = get_uri_for_curie_id(dataset_curie)
        elif (
            n_url_path_components == 7
        ):  # /s/datasets/{dataset_curie}/collections/{collection_curie}/items
            dataset_curie = values.get("dataset_curie")
            collection_curie = values.get("collection_curie")
            values["general_class"] = GEO.Feature
            values[
                "link_constructor"
            ] = f"/s/datasets/{dataset_curie}/collections/{collection_curie}/items"
            values["classes"] = frozenset([PREZ.FeatureList])
            values["uri"] = get_uri_for_curie_id(collection_curie)
        return values


def get_uri(dataset_curie, collection_curie=None):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        PREFIX prez: <{PREZ}>
        PREFIX xsd: <{XSD}>

        SELECT ?fc ?d {{
            ?d dcterms:identifier "{dataset_curie}"^^prez:slug ;
                    a dcat:Dataset .
            {f'''?fc dcterms:identifier "{collection_curie}"^^prez:slug ;
                    a geo:FeatureCollection .
                ?d rdfs:member ?fc .''' if collection_curie else ""}
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
