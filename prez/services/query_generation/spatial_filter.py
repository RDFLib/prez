from decimal import Decimal
from typing import List

from rdf2geojson.contrib.geomet.util import flatten_multi_dim
from rdf2geojson.contrib.geomet.wkt import dumps
from rdflib.namespace import GEO
from sparql_grammar_pydantic import (
    IRI,
    ArgList,
    Constraint,
    Expression,
    Filter,
    FunctionCall,
    GraphPatternNotTriples,
    PrimaryExpression,
    RDFLiteral,
    TriplesSameSubjectPath,
    Var,
    TriplesBlock,
    DataBlock,
    DataBlockValue,
    InlineData,
    InlineDataOneVar,
    GroupGraphPattern,
    GroupGraphPatternSub,
    ServiceGraphPattern,
    VarOrIri,
    VarOrTerm,
    PropertyListPathNotEmpty,
    GraphTerm,
    BlankNode,
    BlankNodeLabel,
    VerbPath,
    SG_Path,
    PathAlternative,
    PathSequence,
    PathEltOrInverse,
    PathElt,
    PathPrimary,
    ObjectList,
    Object,
    GraphNode, GroupOrUnionGraphPattern, ObjectListPath, ObjectPath, GraphNodePath,
)

from prez.config import settings
from prez.reference_data.cql.geo_function_mapping import (  # Updated import
    cql_sparql_spatial_mapping,
    cql_qlever_spatial_mapping,
    QLSS,
)


def _verb_path_for_iri(iri: str) -> VerbPath:
    return VerbPath(
        path=SG_Path(
            path_alternative=PathAlternative(
                sequence_paths=[
                    PathSequence(
                        list_path_elt_or_inverse=[
                            PathEltOrInverse(
                                path_elt=PathElt(
                                    path_primary=PathPrimary(
                                        value=IRI(
                                            value=iri
                                        )
                                    )
                                )
                            )
                        ]
                    )
                ]
            )
        )
    )

def _object_list_for_iri_or_var_or_lit(iri_or_var_or_lit: IRI | Var | RDFLiteral) -> ObjectList:
    if isinstance(iri_or_var_or_lit, (IRI, RDFLiteral)):
        vot = VarOrTerm(varorterm=GraphTerm(content=iri_or_var_or_lit))
    elif isinstance(iri_or_var_or_lit, Var):
        vot = VarOrTerm(varorterm=iri_or_var_or_lit)
    else:
        raise ValueError("Unsupported type for _object_list_for_iri_or_var_or_lit")
    return ObjectList(
        list_object=[
            Object(
                graphnode=GraphNode(
                    varorterm_or_triplesnode=vot
                )
            )
        ]
    )

def count_decimal_places(num):
    return abs(Decimal(str(num)).as_tuple().exponent)


def find_max_decimals(coordinates):
    max_decimals = 0
    flattened = flatten_multi_dim(coordinates)
    for value in flattened:
        if isinstance(value, (int, float)):
            max_decimals = max(max_decimals, count_decimal_places(value))
    return max_decimals


def get_wkt_from_coords(coordinates, geom_type: str):
    max_decimals = find_max_decimals([(geom_type, coordinates, None)])
    return dumps({"type": geom_type, "coordinates": coordinates}, max_decimals)


def format_coordinates_as_wkt(bbox_values):
    if len(bbox_values) == 4:
        coordinates = [
            [
                [bbox_values[0], bbox_values[1]],
                [bbox_values[0], bbox_values[3]],
                [bbox_values[2], bbox_values[3]],
                [bbox_values[2], bbox_values[1]],
                [bbox_values[0], bbox_values[1]],
            ]
        ]
    else:
        if len(bbox_values) == 6:
            raise NotImplementedError("XYZ bbox not yet supported.")
        else:
            raise ValueError(f"Invalid number of values in bbox ({len(bbox_values)}).")
    return coordinates


def generate_spatial_filter_clause(
    wkt_value: str, # The plain WKT string, e.g. "POLYGON((...))"
    subject_var: Var, # The SPARQL variable for the subject, e.g. Var(value="focus_node")
    geom_bnode_var: Var,
    geom_wkt_lit_var: Var,
    cql_operator: str,
    target_system: str,
) -> List[GraphPatternNotTriples]:
    """
    Generates SPARQL spatial filter clauses (FILTER or SERVICE block).
    Returns a list of GraphPatternNotTriples.
    """
    if target_system == "geosparql":
        if cql_operator not in cql_sparql_spatial_mapping:
            raise NotImplementedError(f"CQL operator {cql_operator} not supported for GeoSPARQL")
        
        filter_gpnt = GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=FunctionCall(
                        iri=IRI(value=cql_sparql_spatial_mapping[cql_operator]),
                        arg_list=ArgList(
                            expressions=[
                                Expression.from_primary_expression(
                                    primary_expression=PrimaryExpression(content=geom_wkt_lit_var)
                                ),
                                Expression.from_primary_expression(
                                    primary_expression=PrimaryExpression(
                                        content=RDFLiteral(
                                            value=wkt_value,  # Use wkt_value directly
                                            datatype=IRI(value=str(GEO.wktLiteral))
                                        )
                                    )
                                )
                            ]
                        )
                    )
                )
            )
        )
        return [filter_gpnt]

    elif target_system == "qlever":
        if cql_operator not in cql_qlever_spatial_mapping:
            raise NotImplementedError(f"CQL operator {cql_operator} not supported for QLever")

        qlever_function_iri = IRI(value=cql_qlever_spatial_mapping[cql_operator])

        values_clause_for_input_wkt = GraphPatternNotTriples(
            content=InlineData(
                data_block=DataBlock(
                    block=InlineDataOneVar(
                        variable=Var(value="wkt_input_for_qlever"), # Dedicated var for QLever input WKT
                        datablockvalues=[
                            DataBlockValue(
                                value=RDFLiteral(
                                    value=wkt_value,
                                    datatype=IRI(
                                        value=str(GEO.wktLiteral)  # Qlever ignores the datatype at present.
                                    )
                                )
                            )
                        ]
                    )
                )
            )
        )

        # Internal graph pattern for QLever SERVICE call
        qlever_internal_ggps = GroupGraphPatternSub(
            graph_patterns_or_triples_blocks=[
                TriplesBlock(
                    triples=TriplesSameSubjectPath(
                        content=(
                            VarOrTerm(varorterm=GraphTerm(content=BlankNode(value=BlankNodeLabel(part_1="config")))),
                            PropertyListPathNotEmpty(
                                first_pair=(
                                    _verb_path_for_iri(str(QLSS.algorithm)),
                                    ObjectListPath(
                                        object_paths=[
                                            ObjectPath(
                                                graph_node_path=GraphNodePath(
                                                    varorterm_or_triplesnodepath=VarOrTerm(
                                                        varorterm=GraphTerm(
                                                            content=IRI(
                                                                value=str(QLSS.libspatialjoin)
                                                            )
                                                        )
                                                    )
                                                )
                                            )
                                        ]

                                    )
                                ),
                                other_pairs=[
                                    (_verb_path_for_iri(str(QLSS.left)), _object_list_for_iri_or_var_or_lit(Var(value="wkt_input_for_qlever"))),
                                    (_verb_path_for_iri(str(QLSS.right)), _object_list_for_iri_or_var_or_lit(geom_wkt_lit_var)),
                                    (_verb_path_for_iri(str(QLSS.payload)), _object_list_for_iri_or_var_or_lit(subject_var)),
                                    (_verb_path_for_iri(str(QLSS.joinType)), _object_list_for_iri_or_var_or_lit(qlever_function_iri))
                                ]
                            )
                        )
                    )
                ),
                # Re-declare necessary triples inside QLever's scope
                GraphPatternNotTriples(
                    content=GroupOrUnionGraphPattern(
                        group_graph_patterns=[
                            GroupGraphPattern(
                                content=GroupGraphPatternSub(
                                    graph_patterns_or_triples_blocks=[
                                        TriplesBlock.from_tssp_list(
                                            [
                                                TriplesSameSubjectPath.from_spo(
                                                    subject=subject_var,
                                                    predicate=IRI(value=str(GEO.hasGeometry)),
                                                    object=geom_bnode_var
                                                ),
                                                TriplesSameSubjectPath.from_spo(
                                                    subject=geom_bnode_var,
                                                    predicate=IRI(value=str(GEO.asWKT)),
                                                    object=geom_wkt_lit_var
                                                )
                                            ]
                                        )
                                    ]
                                )
                            )
                        ]
                    )
                )
            ]
        )
        
        qlever_service_gpnt = GraphPatternNotTriples(
            content=ServiceGraphPattern(
                var_or_iri=VarOrIri(varoriri=IRI(value=str(QLSS))),
                group_graph_pattern=GroupGraphPattern(content=qlever_internal_ggps)
            )
        )
        combined_gpnt = GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(
                group_graph_patterns=[
                    GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            graph_patterns_or_triples_blocks=[
                                values_clause_for_input_wkt,
                                qlever_service_gpnt
                            ]
                        )
                    )
                ]
            )
        )
        return [combined_gpnt]

    else:
        raise ValueError(f"Unknown target_system: {target_system}")


def generate_bbox_filter(
    bbox: List[float], filter_crs: str
) -> (List[GraphPatternNotTriples], List[TriplesSameSubjectPath]):
    """
    Original function, wrapper for GeoSPARQL intersection.
    Can be refactored/deprecated later.
    """
    coordinates = format_coordinates_as_wkt(bbox)
    wkt = get_wkt_from_coords(coordinates, "Polygon")

    # Variables for the query
    subject = Var(value="focus_node")
    geom_bn_var = Var(value="geom_bnode_bbox") # Make var names unique if used alongside others
    geom_lit_var = Var(value="geom_var_bbox")

    target_system = settings.spatial_query_format
    if target_system not in ["geosparql", "qlever"]:
        raise NotImplementedError(f"Spatial query format '{target_system}' not supported for CQL.")

    # Triples to define the geometry path
    tssp_list = []
    if target_system == "geosparql":
        tssp_list.append(
            TriplesSameSubjectPath.from_spo(
                subject, IRI(value=GEO.hasGeometry), geom_bn_var
            )
        )
        tssp_list.append(
            TriplesSameSubjectPath.from_spo(geom_bn_var, IRI(value=GEO.asWKT), geom_lit_var)
        )

    filter_gpnts = generate_spatial_filter_clause(
        wkt_value=wkt,
        subject_var=subject,
        geom_bnode_var=geom_bn_var,
        geom_wkt_lit_var=geom_lit_var,
        cql_operator="s_intersects",
        target_system=target_system
    )
    if not filter_gpnts:
        raise ValueError("generate_spatial_filter_clause returned no patterns for GeoSPARQL bbox.")
    
    return filter_gpnts, tssp_list
