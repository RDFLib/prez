from shapely.geometry import mapping
from shapely.ops import orient
from shapely.wkt import loads as load_wkt
from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class SpacePrezFeature(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(DCTERMS.title),
        # str(DCTERMS.description),
    ]
    geom_props = [str(GEO.hasGeometry)]
    hidden_props = [
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
            ?f dcterms:identifier "{id}"^^xsd:token .
            BIND("{id}"^^xsd:token as ?id)
        """

        query_by_uri = f"""
            BIND (<{uri}> as ?f)
            ?f dcterms:identifier ?id .
        """

        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX geo: <{GEO}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            PREFIX xsd: <{XSD}>
            PREFIX dcat: <{DCAT}>
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                ?f a geo:Feature .
                OPTIONAL {{
                    ?f dcterms:title ?title1 .
                }}
                OPTIONAL {{
                    ?f skos:prefLabel ?title2 .
                }}                
                OPTIONAL {{                    
                    ?f rdfs:label ?title3 .
                }}                
                BIND(COALESCE(?title1, ?title2, ?title3, CONCAT("Feature ", STR(?id))) AS ?title)
                OPTIONAL {{
                    ?f dcterms:description ?desc .
                }}
                ?coll a geo:FeatureCollection ;
                    rdfs:member ?f ;
                    dcterms:identifier ?coll_id ;
                    dcterms:title ?coll_label .
                FILTER(lang(?coll_label) = "" || lang(?coll_label) = "en")
                ?d a dcat:Dataset ;
                    dcterms:identifier ?d_id ;
                    dcterms:title ?d_label .
                FILTER(lang(?d_label) = "" || lang(?d_label) = "en")
            }}
        """
        )
        self.graph.bind("geo", GEO)
        self.most_specific_class = most_specific_class
        result = r.bindings[0]
        self.uri = result["f"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"] if result.get("desc") else None
        self.collection = {
            "uri": result["coll"],
            "id": result["coll_id"],
            "title": result["coll_label"],
        }
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
            "collection": self.collection,
            "dataset": self.dataset,
        }

    def to_geojson(self) -> Dict:
        """Returns the GeoJSON representation for the OpenAPI profile"""
        r = self.graph.query(
            f"""
            PREFIX geo: <{GEO}>
            SELECT ?geojson ?wkt
            WHERE {{
                <{self.uri}> geo:hasGeometry/geo:asWKT ?wkt .
                OPTIONAL {{ <{self.uri}> geo:hasGeometry/geo:asGeoJSON ?geojson }}                
            }}
            """
        )
        # see if this Geometry has GeoJSON and, if it has, return it
        geojson_str = r.bindings[0].get("geojson")
        if geojson_str is not None:
            geojson = json.loads(geojson_str)
        else:  # if it doesn't use the WKT, which is required to be present
            wkt = r.bindings[0].get("wkt")
            geojson = mapping(orient(load_wkt(wkt)))
        return {
            "type": "Feature",
            "id": self.id,
            "geometry": geojson,
            "properties": {},
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        props_dict.sort(key=lambda x: float(x["order"]) if x["order"] else 100)
        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        geom_props = []
        type_props = []
        other_props = []

        for prop in props_dict:
            hidden = self.graph.value(
                subject=self.graph.value(
                    predicate=SH.path, object=URIRef(prop["value"])
                ),
                predicate=DASH.hidden,
            )
            if not hidden:
                if prop["value"] in SpacePrezFeature.main_props:
                    main_props.append(prop)
                elif prop["value"] == str(RDF.type):
                    for i, obj in enumerate(prop["objects"]):
                        if obj["value"] == self.most_specific_class:
                            retain_index = i
                            break
                    prop["objects"] = [prop["objects"][retain_index]]
                    type_props.append(prop)
                else:
                    # geom props get added here IF specified in profile
                    other_props.append(prop)

            if prop["value"] in SpacePrezFeature.geom_props:
                for bnode in prop["objects"][0]["rows"]:
                    bnode_prop_name = bnode["value"].split("#")[1]
                    if bnode_prop_name in ["asDGGS", "asGeoJSON", "asWKT"]:
                        self.geometries[bnode_prop_name] = bnode["objects"][0]["value"]

        # sorts & combines into a single list
        properties.extend(main_props)
        properties.extend(geom_props)
        properties.extend(type_props)
        properties.extend(other_props)
        return properties
