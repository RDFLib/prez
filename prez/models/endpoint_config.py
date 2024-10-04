from typing import List, Literal

from pydantic import BaseModel, field_validator
from rdflib import URIRef


class HierarchyItem(BaseModel):
    rdfClass: str
    className: str
    hierarchyLevel: int

    @classmethod
    @field_validator("rdfClass")
    def validate_uri(cls, v: str) -> str:
        try:
            URIRef(v)
            return v
        except ValueError as e:
            raise ValueError(f"Invalid URI: {v}. Error: {str(e)}")


class Relation(BaseModel):
    levelFrom: int
    levelTo: int
    direction: Literal["outbound", "inbound"]
    rdfPredicate: str

    @classmethod
    @field_validator("rdfPredicate")
    def validate_uri(cls, v: str) -> str:
        try:
            URIRef(v)
            return v
        except ValueError as e:
            raise ValueError(f"Invalid URI: {v}. Error: {str(e)}")


class HierarchyRelation(BaseModel):
    name: str
    hierarchy: List[HierarchyItem]
    relations: List[Relation]

    @classmethod
    @field_validator("relations")
    def validate_relations_count(
        cls, v: List[Relation], values: dict
    ) -> List[Relation]:
        hierarchy = values.get("hierarchy")
        if hierarchy and len(v) != len(hierarchy) - 1:
            raise ValueError(
                f"Number of relations ({len(v)}) should be one less than the number of hierarchy items ({len(hierarchy)})"
            )
        return v


class Route(BaseModel):
    name: str
    fullApiPath: str
    hierarchiesRelations: List[HierarchyRelation]


class RootModel(BaseModel):
    routes: List[Route]


configure_endpoings_example = {
    "configName": "Prez Example Endpoint Configuration",
    "routes": [
        {
            "name": "Single hierarchy with Datasets within Catalogs",
            "fullApiPath": "/catalogs/{catalogId}/datasets/{datasetId}",
            "hierarchiesRelations": [
                {
                    "name": "Catalogue of Datasets",
                    "hierarchy": [
                        {
                            "rdfClass": "http://www.w3.org/ns/dcat#Catalog",
                            "className": "Catalog",
                            "hierarchyLevel": 1,
                        },
                        {
                            "rdfClass": "http://www.w3.org/ns/dcat#Dataset",
                            "className": "DCAT Dataset",
                            "hierarchyLevel": 2,
                        },
                    ],
                    "relations": [
                        {
                            "levelFrom": 1,
                            "levelTo": 2,
                            "direction": "outbound",
                            "rdfPredicate": "http://purl.org/dc/terms/hasPart",
                        }
                    ],
                }
            ],
        }
    ],
}
