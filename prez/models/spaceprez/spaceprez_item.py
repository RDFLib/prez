from fastapi import APIRouter
from pydantic import BaseModel, root_validator

from prez.services.spaceprez_service import *

PREZ = Namespace("https://surroundaustralia.com/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


class Item(BaseModel):
    id: Optional[str]
    uri: Optional[URIRef]
    general_class: Optional[URIRef]
    children_general_class: Optional[URIRef]
    feature_id: Optional[str]
    feature_classes: Optional[List[URIRef]]  # TODO make generic not just for features
    collection_id: Optional[str]
    dataset_id: Optional[str]
    parent_id: Optional[str]
    parent_uri: Optional[URIRef]
    classes: Optional[URIRef]

    @root_validator
    def populate(cls, values):
        dataset_id = values.get("dataset_id")
        collection_id = values.get("collection_id")
        feature_id = values.get("feature_id")
        if dataset_id:
            q = f"""
                PREFIX dcat: <{DCAT}>
                PREFIX dcterms: <{DCTERMS}>
                PREFIX geo: <{GEO}>
                PREFIX rdfs: <{RDFS}>
                PREFIX xsd: <{XSD}>

                SELECT ?f ?fc ?d ?class {{
                    ?d dcterms:identifier "{dataset_id}"^^xsd:token ;
                            a dcat:Dataset .
                    {f'''?fc dcterms:identifier "{collection_id}"^^xsd:token ;
                            a geo:FeatureCollection .
                        ?d rdfs:member ?fc .''' if collection_id else ""}
                    {f'''?f dcterms:identifier "{feature_id}"^^xsd:token ;
                            a geo:Feature ;
                            a ?class .
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
                    values["classes"] = [c["class"]["value"] for c in r[1]]
                elif fc:
                    values["id"] = collection_id
                    values["uri"] = URIRef(fc["value"])
                    values["general_class"] = GEO.FeatureCollection
                    values["children_general_class"] = GEO.Feature
                    values["parent_uri"] = URIRef(d["value"])
                    values["parent_id"] = dataset_id
                else:
                    values["id"] = dataset_id
                    values["uri"] = URIRef(d["value"])
                    values["general_class"] = DCAT.Dataset
                    values["children_general_class"] = GEO.FeatureCollection
        return values
