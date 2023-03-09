from typing import Optional
from typing import Set

from pydantic import BaseConfig
from pydantic import BaseModel, root_validator
from rdflib import Namespace, URIRef
from rdflib.namespace import DCTERMS, XSD, DCAT, GEO, RDFS

from prez.sparql.methods import sparql_query_non_async

PREZ = Namespace("https://prez.dev/")

BaseConfig.arbitrary_types_allowed = True


class SpatialItem(BaseModel):
    id: Optional[str]
    uri: Optional[URIRef]
    url_path: Optional[str]
    general_class: Optional[URIRef]
    feature_id: Optional[str]
    collection_id: Optional[str]
    dataset_id: Optional[str]
    parent_id: Optional[str]
    parent_uri: Optional[URIRef]
    classes: Optional[Set[URIRef]]
    link_constructor: Optional[str]
    selected_class: Optional[URIRef] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        dataset_id = values.get("dataset_id")
        collection_id = values.get("collection_id")
        feature_id = values.get("feature_id")
        uri = values.get("uri")
        if uri:
            q = f"""SELECT ?class {{ <{uri}> a ?class }}"""
            r = sparql_query_non_async(q, "SpacePrez")
            if r[0] and r[1]:
                # set the uri of the item
                values["classes"] = frozenset([c["class"]["value"] for c in r[1]])
            else:
                raise ValueError(
                    f"Could not find a class for {uri}, or URI does not exist in SpacePrez"
                )
            return values
        elif dataset_id:
            q = f"""
                PREFIX dcat: <{DCAT}>
                PREFIX dcterms: <{DCTERMS}>
                PREFIX geo: <{GEO}>
                PREFIX prez: <{PREZ}>
                PREFIX rdfs: <{RDFS}>
                PREFIX xsd: <{XSD}>

                SELECT ?f ?fc ?d ?f_class ?fc_class ?d_class {{
                    ?d dcterms:identifier "{dataset_id}"^^prez:slug ;
                            a dcat:Dataset ;
                            a ?d_class .
                    {f'''?fc dcterms:identifier "{collection_id}"^^prez:slug ;
                            a geo:FeatureCollection ;
                            a ?fc_class .
                        ?d rdfs:member ?fc .''' if collection_id else ""}
                    {f'''?f dcterms:identifier "{feature_id}"^^prez:slug ;
                            a geo:Feature ;
                            a ?f_class .
                        ?fc rdfs:member ?f .''' if feature_id else ""}
                }}
                """
            r = sparql_query_non_async(q, "SpacePrez")
            if r[0]:
                # set the uri of the item
                f = r[1][0].get("f")
                fc = r[1][0].get("fc")
                d = r[1][0].get("d")
                if f:
                    values["id"] = feature_id
                    values["uri"] = URIRef(f["value"])
                    values["general_class"] = GEO.Feature
                    values["parent_uri"] = URIRef(fc["value"])
                    values["parent_id"] = collection_id
                    values["classes"] = frozenset([c["f_class"]["value"] for c in r[1]])
                elif fc:
                    values["id"] = collection_id
                    values["uri"] = URIRef(fc["value"])
                    values["general_class"] = GEO.FeatureCollection
                    values["parent_uri"] = URIRef(d["value"])
                    values["parent_id"] = dataset_id
                    values[
                        "link_constructor"
                    ] = f"/s/datasets/{dataset_id}/collections/{collection_id}/items"
                    values["classes"] = frozenset(
                        [c["fc_class"]["value"] for c in r[1]]
                    )
                else:
                    values["id"] = dataset_id
                    values["uri"] = URIRef(d["value"])
                    values["general_class"] = DCAT.Dataset
                    values["link_constructor"] = f"/s/datasets/{dataset_id}/collections"
                    values["classes"] = frozenset([c["d_class"]["value"] for c in r[1]])
        return values
