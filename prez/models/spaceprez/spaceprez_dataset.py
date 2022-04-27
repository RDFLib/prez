from typing import List, Dict, Optional

from rdflib import Graph
from rdflib.namespace import DCTERMS, SKOS, RDFS

from config import *
from models import PrezModel


class SpacePrezDataset(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(DCTERMS.title),
        # str(DCTERMS.description),
    ]
    geom_props = [str(GEO.hasBoundingBox)]
    hidden_props = [
        str(DCTERMS.identifier),
        str(RDFS.seeAlso),
        str(DCTERMS.description),
    ]

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
            ?d dcterms:identifier ?id .
            FILTER (STR(?id) = "{id}")
        """

        query_by_uri = f"""
            BIND (<{uri}> as ?d) 
            ?d dcterms:identifier ?id .
        """

        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                ?d a dcat:Dataset ;
                    dcterms:title ?title ;
                    dcterms:description ?desc .
                FILTER(lang(?title) = "" || lang(?title) = "en")
            }}
        """
        )

        result = r.bindings[0]
        self.uri = result["d"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"]
        self.geometries = {}

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
            "geometries": self.geometries,
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        geom_props = []
        other_props = []

        for prop in props_dict:
            if prop["value"] in SpacePrezDataset.hidden_props:
                continue
            elif prop["value"] in SpacePrezDataset.main_props:
                main_props.append(prop)
            elif prop["value"] in SpacePrezDataset.geom_props:
                geom_props.append(prop)
                for bnode in prop["objects"][0]["rows"]:
                    bnode_prop_name = bnode["value"].split("#")[1]
                    if bnode_prop_name in ["asDGGS", "asGeoJSON", "asWKT"]:
                        self.geometries[bnode_prop_name] = bnode["objects"][0]["value"]
            else:
                other_props.append(prop)

        # sorts & combines into a single list
        properties.extend(main_props)
        properties.extend(geom_props)
        properties.extend(other_props)

        return properties
