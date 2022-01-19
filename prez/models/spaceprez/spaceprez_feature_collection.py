from typing import List, Dict, Optional

from rdflib import Graph
from rdflib.namespace import DCTERMS, SKOS, RDFS

from config import *
from models import PrezModel


class SpacePrezFeatureCollection(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        DCTERMS.title,
        DCTERMS.description,
    ]
    hidden_props = [
        DCTERMS.identifier,
    ]

    def __init__(
        self,
        graph: Graph,
        id: Optional[str] = None,
        uri: Optional[str] = None,
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
            ?coll dcterms:identifier ?id .
            FILTER (STR(?id) = "{id}")
        """

        query_by_uri = f"""
            BIND (<{uri}> as ?coll) 
            ?coll dcterms:identifier ?id .
        """

        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX geo: <{GEO}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                ?coll a geo:FeatureCollection ;
                    rdfs:label|skos:prefLabel|dcterms:title ?title ;
                    skos:definition|dcterms:description ?desc ;
                    dcterms:isPartOf ?d .
                ?d dcterms:identifier ?d_id ;
                    rdfs:label|skos:prefLabel|dcterms:title ?d_label .
            }}
        """
        )

        result = r.bindings[0]
        self.uri = result["coll"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"]
        self.dataset = {
            "uri": result["d"],
            "id": result["d_id"],
            "title": result["d_label"],
        }

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
            "dataset": self.dataset,
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props_dict()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for uri, prop in props_dict.items():
            if uri in SpacePrezFeatureCollection.hidden_props:
                continue
            elif uri in SpacePrezFeatureCollection.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        properties.extend(
            sorted(
                main_props,
                key=lambda p: self._sort_within_list(p, SpacePrezFeatureCollection.main_props),
            )
        )
        properties.extend(other_props)

        return properties
