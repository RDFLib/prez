from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class CatPrezResource(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(DCTERMS.creator),
        str(DCTERMS.publisher),
        str(DCTERMS.created),
        str(DCTERMS.modified),
    ]
    geom_props = [str(GEO.hasBoundingBox)]
    hidden_props = [
        str(RDF.type),
        str(DCTERMS.identifier),
        str(DCTERMS.title),
        str(DCTERMS.description),
        str(RDFS.label),
        str(DCTERMS.hasPart),
    ]

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
                ?c dcterms:identifier "{id}"^^xsd:token .
                BIND("{id}" AS ?id)
        """

        query_by_uri = f"""
                BIND (<{uri}> as ?cs)
                ?c dcterms:identifier ?id .
        """

        qx = f"""
            PREFIX dcat: <{DCAT}>
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX xsd: <{XSD}>

            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}

                VALUES ?type {{ dcat:Resource dcat:Dataset }}
                ?c
                    a ?type ;
                    dcterms:title ?title ;
                    dcterms:description ?desc .
            }}
            """
        r = self.graph.query(qx)
        result = r.bindings[0]
        self.uri = result["c"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"]

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
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for prop in props_dict:
            if prop["value"] in CatPrezResource.hidden_props:
                continue
            elif prop["value"] in CatPrezResource.main_props:
                main_props.append(prop)
            elif prop["value"] in CatPrezResource.geom_props:
                for bnode in prop["objects"][0]["rows"]:
                    bnode_prop_name = bnode["value"].split("#")[1]
                    if bnode_prop_name in ["asDGGS", "asGeoJSON", "asWKT"]:
                        self.geometries[bnode_prop_name] = bnode["objects"][0]["value"]
            else:
                other_props.append(prop)

        # sorts & combines into a single list
        properties.extend(
            sorted(
                main_props,
                key=lambda p: self._sort_within_list(p, CatPrezResource.main_props),
            )
        )
        properties.extend(other_props)

        return properties
