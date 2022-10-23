from fastapi import APIRouter
from pydantic import BaseModel, root_validator, BaseConfig
from starlette.datastructures import URL

from prez.services.spaceprez_service import *

PREZ = Namespace("https://kurrawong.net/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])

BaseConfig.arbitrary_types_allowed = True


class Item(BaseModel):
    id: Optional[str]
    uri: Optional[URIRef]
    general_class: Optional[URIRef]
    children_general_class: Optional[URIRef] = DCAT.Dataset
    feature_id: Optional[str]
    feature_classes: Optional[List[URIRef]]  # TODO make generic not just for features
    collection_id: Optional[str]
    dataset_id: Optional[str]
    parent_id: Optional[str]
    parent_uri: Optional[URIRef]
    classes: Optional[URIRef]
    link_constructor: Optional[str] = "/dataset/"

    @root_validator
    def populate(cls, values):
        dataset_id = values.get("dataset_id")
        collection_id = values.get("collection_id")
        feature_id = values.get("feature_id")
        uri = values.get("uri")
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
                    values[
                        "link_constructor"
                    ] = f"/dataset/{dataset_id}/collections/{collection_id}/items/"
                else:
                    values["id"] = dataset_id
                    values["uri"] = URIRef(d["value"])
                    values["general_class"] = DCAT.Dataset
                    values["children_general_class"] = GEO.FeatureCollection
                    values["link_constructor"] = f"/dataset/{dataset_id}/collections/"
        elif uri:  # uri provided, get the ID
            q = f"""
                    PREFIX dcterms: <{DCTERMS}>

                    SELECT ?id {{
                        <{uri}> dcterms:identifier ?id ;
                        FILTER(DATATYPE(?id) = xsd:token)
                    }}
                    """
            r = sparql_query_non_async(q, "SpacePrez")
            if r[0]:
                values["id"] = r[1][0]["id"]["value"]
        return values
