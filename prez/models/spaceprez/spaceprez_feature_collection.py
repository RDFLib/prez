from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class SpacePrezFeatureCollection(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(DCTERMS.title),
        # str(DCTERMS.description),
    ]
    geom_props = [str(GEO.hasBoundingBox)]
    hidden_props = [
        str(DCTERMS.identifier),
        str(RDFS.member),
        str(DCTERMS.description),
    ]

    def __init__(
        self,
        graph: Graph,
        id: Optional[str] = None,
        uri: Optional[str] = None,
        most_specific_class: Optional[str] = None,
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
                ?coll dcterms:identifier "{id}"^^xsd:token .
                BIND ("{id}"^^xsd:token as ?id)
        """

        query_by_uri = f"""
                BIND (<{uri}> as ?coll)
                ?coll dcterms:identifier ?id .
        """

        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX geo: <{GEO}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            PREFIX xsd: <{XSD}>
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                ?d rdfs:member ?coll ;
                    dcterms:identifier ?d_id ;
                    dcterms:title ?d_label .
                FILTER(lang(?d_label) = "" || lang(?d_label) = "en")
                ?coll a geo:FeatureCollection ;
                    dcterms:title ?title ;
                    dcterms:description ?desc .
                FILTER(lang(?title) = "" || lang(?title) = "en")
            }}
        """
        r = self.graph.query(q)
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
            "dataset": self.dataset,
        }

    def to_geojson(self) -> Dict:
        """Returns the GeoJSON representation for the OpenAPI profile"""
        r = self.graph.query(
            f"""
            PREFIX geo: <{GEO}>
            SELECT ?bbox
            WHERE {{
                BIND (<{self.uri}> as ?fc)
                ?fc geo:hasBoundingBox/geo:asGeoJSON ?bbox .
            }}
        """
        )

        bbox = r.bindings[0].get("bbox")

        g_dict = {
            "type": "FeatureCollection",
            "features": [],  # have all features' geojson? need to query for all & call feature.to_geojson()
        }

        if bbox is not None:
            g_dict["bbox"] = json.loads(bbox)["coordinates"][0]

        return g_dict

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        geom_props = []
        other_props = []

        for prop in props_dict:
            if prop["value"] in SpacePrezFeatureCollection.hidden_props:
                continue
            elif prop["value"] in SpacePrezFeatureCollection.main_props:
                main_props.append(prop)
            elif prop["value"] in SpacePrezFeatureCollection.geom_props:
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
