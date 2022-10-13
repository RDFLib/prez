from fastapi import APIRouter
from pydantic import BaseModel

from prez.services.spaceprez_service import *

PREZ = Namespace("https://surroundaustralia.com/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


class Item(BaseModel):
    id: Optional[str]
    uri: Optional[URIRef]
    feature_id: Optional[str]
    feature_classes: Optional[List[URIRef]]
    feature_collection_id: Optional[str]
    dataset_id: Optional[str]
    parent_id: Optional[str]
    parent_uri: Optional[URIRef]
    children_general_class: Optional[URIRef]

    def populate(self):
        if self.dataset_id:
            q = f"""
                PREFIX dcat: <{DCAT}>
                PREFIX dcterms: <{DCTERMS}>
                PREFIX geo: <{GEO}>
                PREFIX rdfs: <{RDFS}>
                PREFIX xsd: <{XSD}>

                SELECT ?f ?fc ?d ?class {{
                    ?d dcterms:identifier "{self.dataset_id}"^^xsd:token ;
                            a dcat:Dataset .
                    {f'''?fc dcterms:identifier "{self.collection_id}"^^xsd:token ;
                            a geo:FeatureCollection .
                        ?d rdfs:member ?fc .''' if self.collection_id else ""}
                    {f'''?f dcterms:identifier "{self.feature_id}"^^xsd:token ;
                            a geo:Feature ;
                            a ?class .
                        ?fc rdfs:member ?f .''' if self.feature_id else ""}
                }}
                """
            r = sparql_query_non_async(q, "SpacePrez")
            if r[0]:
                self.uri = r[1][0].get("f", r[1][0].get("fc", r[1][0].get("fc")))
                f = r[1][0].get("f", None)
                if f:  # find feature classes
                    self.children_general_class = [c["class"]["value"] for c in r[1]]
