import json

from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class SpacePrezDataset(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(DCTERMS.title),
        # str(DCTERMS.description),
    ]
    geom_props = [str(GEO.hasBoundingBox), str(DCTERMS.spatial)]
    hidden_props = [
        str(DCTERMS.identifier),
        str(RDFS.seeAlso),
        str(DCTERMS.description),
    ]

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)

        self.uri = None
        self.id = None
        self.title = None
        self.description = None
        self.collections = []

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
            ?d dcterms:identifier "{id}"^^xsd:token .
            BIND("{id}" AS ?id)
        """

        query_by_uri = f"""
            BIND (<{uri}> as ?d)
            ?d dcterms:identifier ?id .
        """

        r = self.graph.query(
            f"""
            PREFIX dcat: <{DCAT}>
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                ?d a dcat:Dataset ;
                    dcterms:title ?title ;
                    dcterms:description ?desc ;
                    rdfs:member ?coll .
                ?coll dcterms:identifier ?coll_id ;
                    dcterms:title ?coll_title .
                FILTER(lang(?title) = "" || lang(?title) = "en")
            }}
        """
        )

        for result in r.bindings:
            if self.uri is None:
                self.uri = result["d"]
            if self.id is None:
                self.id = result["id"]
            if self.title is None:
                self.title = result["title"]
            if self.description is None:
                self.description = result["desc"]
            self.collections.append(
                {
                    "id": result["coll_id"],
                    "title": result["coll_title"],
                }
            )

        self.geometries = {
            "asDGGS": None,
            "asGeoJSON": None,
            "asWKT": None,
        }

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
            "geometries": self.geometries,
            "collections": self.collections,
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
                    if bnode_prop_name in ["asDGGS", "asGeoJSON", "asWKT", "bbox"]:
                        self.geometries[bnode_prop_name] = bnode["objects"][0]["value"]
                    elif bnode_prop_name == "geometry":  # for locn:geometry
                        self.geometries["asGeoJSON"] = bnode["objects"][0][
                            "value"
                        ]  # assume locn:geometry is geojson
            else:
                other_props.append(prop)

        # sorts & combines into a single list
        properties.extend(main_props)
        properties.extend(geom_props)
        properties.extend(other_props)

        return properties

    def to_geojson(self) -> Dict:
        """Returns the GeoJSON representation for the OGC API Feature Core profile"""
        d = self.to_dict()
        g = {
            "title": d["title"],
            "description": d["description"],
            "id": d["id"],
            "uri": d["uri"],
            "geometry": json.loads(d["geometries"]["asGeoJSON"]),
            "properties": {
                "@context": {
                    "geo": "http://www.opengis.net/ont/geosparql#",
                    "dcterms": "http://purl.org/dc/terms/",
                    "source": "dcterms:source",
                }
            },
        }
        for prop in d["properties"]:
            if prop["value"] == "http://purl.org/dc/terms/source":
                g["properties"]["source"] = prop["objects"][0]["value"]

        return g
