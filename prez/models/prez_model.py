import json
import re
from abc import ABCMeta, abstractmethod
from typing import Dict, List, Union, Optional

from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDFS, DCTERMS, SH
from shapely.geometry import mapping
from shapely.ops import orient
from shapely.wkt import loads

from prez.config import GEO


class PrezModel(object, metaclass=ABCMeta):
    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.uri = URIRef("")

    @abstractmethod
    def to_dict(self) -> Dict:
        pass

    @abstractmethod
    def _get_properties(self) -> List:
        """Groups properties into specified groups (or hides them) and sorts accordingly"""
        pass

    # currently not being used
    def _sort_within_list(self, prop: Dict, prop_list: List[str]) -> int:
        """Ensures props are sorted in-order within class-specific property groups"""
        if prop.get("uri") in prop_list:
            return prop_list.index(prop["uri"])
        else:
            return len(prop_list)

    # currently not being used
    def _get_prefix(self, var) -> Union[str, None]:
        if isinstance(var, URIRef):
            prefix = var.n3(self.graph.namespace_manager)
            if re.match("<.+>", prefix):  # IRI, not a prefix
                return None
            else:
                return prefix
        else:
            return None

    def _get_props(self) -> List:
        """Returns a list of properties as dictionaries for HTML rendering"""
        table = Table(self.graph, self.uri)
        return table.to_dict()


class PredCell:
    """Represents a HTML table cell for a predicate"""

    def __init__(
        self,
        value: str,
        qname: str,
        label: str,
        description: Optional[str] = None,
        explanation: Optional[str] = None,
        pgroup: Optional[str] = None,
        porder: Optional[int] = None,
    ):
        self.value = value
        self.qname = qname
        self.label = label
        self.description = description
        self.explanation = explanation
        self.objects = []
        self.pgroup = pgroup
        self.order = porder

    def __repr__(self):
        return f"{self.qname}"

    def to_dict(self) -> Dict:
        """Returns the dictionary representation for HTML display"""
        return {
            "value": self.value,
            "qname": self.qname,
            "label": self.label,
            "description": self.description,
            "explanation": self.explanation,
            "objects": [obj.to_dict() for obj in self.objects],
            "pgroup": self.pgroup,
            "order": self.order,
        }


class ObjCell:
    """Represents a HTML table cell for an object"""

    def __init__(
        self,
        value: str,
        qname: str,
        label: str,
        description: Optional[str] = None,
        datatype: Optional[str] = None,
        langtag: Optional[str] = None,
    ):
        self.value = value
        self.qname = qname
        self.label = label
        self.description = description
        self.datatype = datatype
        self.langtag = langtag
        self.rows = []

    def __repr__(self):
        if self.qname:
            return self.qname
        else:
            return self.value

    def to_dict(self) -> Dict:
        """Returns the dictionary representation for HTML display"""
        return {
            "value": self.value,
            "qname": self.qname,
            "label": self.label,
            "description": self.description,
            "datatype": self.datatype,
            "langtag": self.langtag,
            "rows": [row.to_dict() for row in self.rows],
        }

    def get_pred(self, p: str) -> Union[PredCell, None]:
        """Returns a PredCell object in the rows list if it exists, else returns None"""
        for pred in self.rows:
            if pred.value == p:
                return pred
        return None

    def populate(self, graph: Graph, subject: Union[URIRef, BNode]) -> None:
        """Recursively populates the rows for this object cell"""
        for p, o in graph.predicate_objects(subject):
            datatype = None
            if (
                isinstance(o, Literal) and o.datatype is not None
            ):  # attempts to get object qname
                datatype = {
                    "value": o.datatype,
                    "qname": graph.namespace_manager.qname(o.datatype),
                    "label": graph.value(
                        subject=o.datatype, predicate=RDFS.label
                    ),  # might need to add a line to SPARQL query to get label?
                }

            qname = None
            if isinstance(o, URIRef):
                try:
                    qname = graph.namespace_manager.qname(o)
                except ValueError:
                    pass

            obj = ObjCell(
                value=o.__str__(),
                qname=qname,
                label=graph.value(subject=o, predicate=RDFS.label),
                description=graph.value(subject=o, predicate=DCTERMS.description),
                datatype=datatype,
                langtag=o.language if isinstance(o, Literal) else None,
            )

            if isinstance(o, BNode):  # recursion for nested properties
                obj.populate(graph, o)

            pred = self.get_pred(p.__str__())

            if pred is None:
                shape_bn = graph.value(predicate=SH.path, object=p)
                # nodeshape = graph.value(predicate=SH.property, object=shape_bn)
                # closed_profile = graph.value(subject=nodeshape, predicate=SH.closed)
                # if (closed_profile == Literal("true", datatype=URIRef(XSD.boolean)) and shape_bn) or \
                #         (closed_profile == Literal("false", datatype=URIRef(XSD.boolean))) or \
                #         (closed_profile is None):
                pred = PredCell(
                    value=p.__str__(),
                    qname=graph.namespace_manager.qname(p),
                    label=graph.value(subject=p, predicate=RDFS.label),
                    description=graph.value(subject=p, predicate=DCTERMS.description),
                    explanation=graph.value(subject=p, predicate=DCTERMS.provenance),
                    pgroup=graph.value(subject=shape_bn, predicate=SH.group),
                    porder=graph.value(subject=shape_bn, predicate=SH.order),
                )
                pred.objects.append(obj)
                self.rows.append(pred)
            else:
                pred.objects.append(obj)


class Table(ObjCell):
    """Represents a HTML table"""

    def __init__(self, graph: Graph, uri: URIRef):
        super().__init__(value=uri, qname=None, label=None, datatype=None, langtag=None)
        self.uri = uri
        self.graph = graph
        self.add_geojson_from_wkt()
        self.populate(graph, uri)

    def __repr__(self):
        return f'Table of data for "{self.uri}"'

    # override
    def to_dict(self) -> List:
        return [row.to_dict() for row in self.rows]

    def add_geojson_from_wkt(self):
        """Adds a geojson property to the table if the data has a wkt property but not geojson
        NB table will only be called when rendering HTML views, so the geojson is not added to any RDF or other formats
        """
        has_geometry_bnodes = list(
            self.graph.objects(subject=self.uri, predicate=GEO.hasGeometry)
        )
        has_bounding_box_bnodes = list(
            self.graph.objects(subject=self.uri, predicate=GEO.hasBoundingBox)
        )
        geom_instances_bnodes = has_geometry_bnodes + has_bounding_box_bnodes
        for bnode in geom_instances_bnodes:
            wkt_literal = self.graph.value(subject=bnode, predicate=GEO.asWKT)
            geojson_literal = self.graph.value(subject=bnode, predicate=GEO.asGeoJSON)
            if wkt_literal and not geojson_literal:
                geojson_text = json.dumps(mapping(orient(loads(str(wkt_literal)))))
                geojson_literal = Literal(
                    geojson_text, datatype=URIRef(GEO.geoJSONLiteral)
                )
                self.graph.add((bnode, GEO.asGeoJSON, geojson_literal))
                self.graph.add(
                    (GEO.asGeoJSON, RDFS.label, Literal("as GeoJSON", lang="en"))
                )
                self.graph.add(
                    (
                        GEO.asGeoJSON,
                        DCTERMS.description,
                        Literal("The GeoJSON serialization of a Geometry", lang="en"),
                    )
                )
