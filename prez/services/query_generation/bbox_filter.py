from typing import List

from rdflib.namespace import GEO
from sparql_grammar_pydantic import (
    ArgList,
    FunctionCall,
    IRI,
    Var,
    GraphPatternNotTriples,
    Expression,
    PrimaryExpression,
    TriplesSameSubjectPath,
    RDFLiteral,
    Filter,
    Constraint,
)

from prez.reference_data.cql.geo_function_mapping import GEOF
from prez.services.query_generation.cql import (
    get_wkt_from_coords,
    format_coordinates_as_wkt,
)


def generate_bbox_filter(
    bbox: List[float], filter_crs: str
) -> (GraphPatternNotTriples, List[TriplesSameSubjectPath]):
    coordinates = format_coordinates_as_wkt(bbox)
    wkt = get_wkt_from_coords(coordinates, "Polygon")

    wkt_with_crs = f"<{filter_crs}> {wkt}"
    subject = Var(value="focus_node")
    geom_bn_var = Var(value="geom_bnode")
    geom_lit_var = Var(value="geom_var")
    tssp_list = []
    tssp_list.append(
        TriplesSameSubjectPath.from_spo(
            subject, IRI(value=GEO.hasGeometry), geom_bn_var
        )
    )
    tssp_list.append(
        TriplesSameSubjectPath.from_spo(geom_bn_var, IRI(value=GEO.asWKT), geom_lit_var)
    )

    geom_func_iri = IRI(value=GEOF.sfIntersects)
    geom_1_exp = Expression.from_primary_expression(
        primary_expression=PrimaryExpression(content=geom_lit_var)
    )
    geom_2_datatype = IRI(value="http://www.opengis.net/ont/geosparql#wktLiteral")
    geom_2_exp = Expression.from_primary_expression(
        primary_expression=PrimaryExpression(
            content=RDFLiteral(value=wkt_with_crs, datatype=geom_2_datatype)
        )
    )
    arg_list = ArgList(expressions=[geom_1_exp, geom_2_exp])
    fc = FunctionCall(iri=geom_func_iri, arg_list=arg_list)

    spatial_filter = Filter(constraint=Constraint(content=fc))
    filter_gpnt = GraphPatternNotTriples(content=spatial_filter)
    return filter_gpnt, tssp_list
