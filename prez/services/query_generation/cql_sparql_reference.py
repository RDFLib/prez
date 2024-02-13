from rdflib import Namespace
from shapely import (
    Polygon,
    MultiPolygon,
    Point,
    MultiPoint,
    LineString,
    MultiLineString,
)

GEOF = Namespace("http://www.opengis.net/def/function/geosparql/")

cql_sparql_spatial_mapping = {
    "s_intersects": GEOF.sfIntersects,
    "s_within": GEOF.sfWithin,
    "s_contains": GEOF.sfContains,
    "s_disjoint": GEOF.sfDisjoint,
    "s_equals": GEOF.sfEquals,
    "s_overlaps": GEOF.sfOverlaps,
    "s_touches": GEOF.sfTouches,
    "s_crosses": GEOF.sfCrosses,
}

cql_to_shapely_mapping = {
    "Polygon": Polygon,
    "MultiPolygon": MultiPolygon,
    "Point": Point,
    "MultiPoint": MultiPoint,
    "LineString": LineString,
    "MultiLineString": MultiLineString,
}
