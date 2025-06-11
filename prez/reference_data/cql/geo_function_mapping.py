from rdflib import Namespace
from rdflib.namespace import GEO

GEOF = Namespace("http://www.opengis.net/def/function/geosparql/")
QLSS = Namespace("https://qlever.cs.uni-freiburg.de/spatialSearch/")

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

cql_qlever_spatial_mapping = {
    "s_intersects": QLSS.intersects,
    "s_within": QLSS.within,
    "s_contains": QLSS.contains,
    "s_disjoint": QLSS.disjoint,
    "s_equals": QLSS.equals,
    "s_overlaps": QLSS.overlaps,
    "s_touches": QLSS.touches,
    "s_crosses": QLSS.crosses,
}

cql_graphdb_spatial_properties = {
    "s_intersects": GEO.sfIntersects,
    "s_within": GEO.sfWithin,
    "s_contains": GEO.sfContains,
    "s_disjoint": GEO.sfDisjoint,
    "s_equals": GEO.sfEquals,
    "s_overlaps": GEO.sfOverlaps,
    "s_touches": GEO.sfTouches,
    "s_crosses": GEO.sfCrosses,
}
