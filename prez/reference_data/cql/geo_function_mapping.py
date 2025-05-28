from rdflib import Namespace

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
