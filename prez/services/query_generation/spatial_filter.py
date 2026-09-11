from decimal import Decimal
from typing import List

from rdf2geojson.contrib.geomet.util import flatten_multi_dim
from rdf2geojson.contrib.geomet.wkt import dumps
from rdflib.namespace import GEO
from sparql_grammar import (
    BLANK_NODE_LABEL,
    IRI,
    ArgList,
    Bind,
    BuiltInCall,
    Expression,
    Filter,
    FunctionCall,
    GraphPatternNotTriples,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    InlineData,
    InlineDataOneVar,
    ObjectListPath,
    PathAlternative,
    PropertyListPathNotEmpty,
    RDFLiteral,
    ServiceGraphPattern,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
)

from prez.config import settings
from prez.reference_data.cql.geo_function_mapping import (
    QLSS,
    cql_graphdb_spatial_properties,
    cql_qlever_spatial_mapping,
)
from prez.services.query_generation.grammar_helpers import create_filter_exists


def _bound_filter(var: Var) -> Filter:
    """FILTER(BOUND(?var))"""
    return Filter(Expression.from_primary_expression(BuiltInCall.create("BOUND", var)))


def _not_blanknode_like_literal_filter(var: Var) -> Filter:
    """FILTER(!STRSTARTS(STR(?var), "_")) - skips literals that look like blank nodes."""
    return Filter(
        Expression.negate(
            BuiltInCall.create(
                "STRSTARTS",
                BuiltInCall.create("STR", var),
                RDFLiteral(value="_"),
            )
        )
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


def extract_crs_code(crs_uri):
    if not crs_uri:
        return None

    if crs_uri.startswith("urn:"):
        parts = crs_uri.split(":")
        return parts[-1] if parts else None
    else:
        parts = crs_uri.rstrip("/").split("/")
        return parts[-1] if parts else None


def get_wkt_from_coords(coordinates, geom_type: str, filter_crs):
    max_decimals = find_max_decimals([(geom_type, coordinates, None)])
    srid = extract_crs_code(filter_crs)

    wkt_with_srid = dumps(
        {"type": geom_type, "coordinates": coordinates, "meta": {"srid": srid}},
        max_decimals,
    )
    srid_wkt = wkt_with_srid.split(";")

    if len(srid_wkt) == 1:
        return filter_crs, srid_wkt[0]
    else:
        return filter_crs, srid_wkt[1]


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


def _wkt_literal(wkt_value: str) -> RDFLiteral:
    return RDFLiteral(value=wkt_value, datatype=IRI(value=str(GEO.wktLiteral)))


def generate_spatial_filter_clause(
    wkt_value: str,  # The plain WKT string, e.g. "POLYGON((...))"
    subject_var: Var,  # The SPARQL variable for the subject, e.g. Var(value="focus_node")
    geom_bnode_var: Var,
    geom_wkt_lit_var: Var,
    cql_operator: str,
    target_system: str,
) -> List[GraphPatternNotTriples]:
    """
    Generates SPARQL spatial filter clauses (FILTER or SERVICE block).
    Returns a list of graph patterns.
    """
    if target_system == "geosparql":
        if cql_operator not in cql_graphdb_spatial_properties:
            raise NotImplementedError(
                f"CQL operator {cql_operator} not supported for GeoSPARQL"
            )

        # Get the geo: predicate (e.g., geo:sfIntersects) from the mapping
        spatial_predicate = cql_graphdb_spatial_properties[cql_operator]

        # Create variable for the bound WKT input
        spatial_wkt_input_var = Var(value="spatial_wkt_input")

        # Create FILTER to skip literals that look like blank nodes (e.g., "_:b1")
        non_blanknode_filter_gpnt = _not_blanknode_like_literal_filter(geom_wkt_lit_var)

        # Create BIND clause: BIND("WKT"^^geo:wktLiteral AS ?spatial_wkt_input)
        bind_gpnt = Bind(
            Expression.from_primary_expression(_wkt_literal(wkt_value)),
            spatial_wkt_input_var,
        )

        # Create triple: ?spatial_wkt_input geo:sfIntersects ?geom_wkt_lit_var
        spatial_triple_gpnt = GroupOrUnionGraphPattern(
            [
                GroupGraphPattern(
                    GroupGraphPatternSub(
                        [
                            TriplesBlock(
                                [
                                    TriplesSameSubjectPath.from_spo(
                                        spatial_wkt_input_var,
                                        IRI(value=str(spatial_predicate)),
                                        geom_wkt_lit_var,
                                    )
                                ]
                            )
                        ]
                    )
                )
            ]
        )

        return [non_blanknode_filter_gpnt, bind_gpnt, spatial_triple_gpnt]

    elif target_system == "qlever":
        if cql_operator not in cql_qlever_spatial_mapping:
            raise NotImplementedError(
                f"CQL operator {cql_operator} not supported for QLever"
            )

        qlever_function_iri = IRI(value=cql_qlever_spatial_mapping[cql_operator])

        # Dedicated var for QLever input WKT. Qlever ignores the datatype at present.
        wkt_input_var = Var(value="wkt_input_for_qlever")
        values_clause_for_input_wkt = InlineData(
            InlineDataOneVar(wkt_input_var, [_wkt_literal(wkt_value)])
        )

        def pair(predicate, obj):
            return (
                PathAlternative.iri(IRI(value=str(predicate))),
                ObjectListPath.create(obj),
            )

        # Internal graph pattern for QLever SERVICE call
        qlever_internal_ggps = GroupGraphPatternSub(
            [
                TriplesBlock(
                    [
                        # _:config qlss:algorithm qlss:libspatialjoin ; qlss:left ... ; ...
                        TriplesSameSubjectPath(
                            BLANK_NODE_LABEL("config"),
                            PropertyListPathNotEmpty(
                                [
                                    pair(
                                        QLSS.algorithm,
                                        IRI(value=str(QLSS.libspatialjoin)),
                                    ),
                                    pair(QLSS.left, wkt_input_var),
                                    pair(QLSS.right, geom_wkt_lit_var),
                                    pair(QLSS.payload, subject_var),
                                    pair(QLSS.joinType, qlever_function_iri),
                                ]
                            ),
                        )
                    ]
                ),
                # Re-declare necessary triples inside QLever's scope
                GroupOrUnionGraphPattern(
                    [
                        GroupGraphPattern(
                            GroupGraphPatternSub(
                                [
                                    TriplesBlock(
                                        [
                                            TriplesSameSubjectPath.from_spo(
                                                subject_var,
                                                IRI(value=str(GEO.hasGeometry)),
                                                geom_bnode_var,
                                            ),
                                            TriplesSameSubjectPath.from_spo(
                                                geom_bnode_var,
                                                IRI(value=str(GEO.asWKT)),
                                                geom_wkt_lit_var,
                                            ),
                                        ]
                                    ),
                                    _not_blanknode_like_literal_filter(
                                        geom_wkt_lit_var
                                    ),
                                ]
                            )
                        )
                    ]
                ),
            ]
        )

        qlever_service_gpnt = ServiceGraphPattern(
            IRI(value=str(QLSS)), GroupGraphPattern(qlever_internal_ggps)
        )
        combined_gpnt = GroupOrUnionGraphPattern(
            [
                GroupGraphPattern(
                    GroupGraphPatternSub(
                        [values_clause_for_input_wkt, qlever_service_gpnt]
                    )
                )
            ]
        )
        return [combined_gpnt]

    else:
        raise ValueError(f"Unknown target_system: {target_system}")


def generate_bbox_filter(
    bbox: List[float], filter_crs: str
) -> (List[GraphPatternNotTriples], List[TriplesSameSubjectPath]):
    """
    Generates spatial filter for a bounding box query parameter, wrapped in a FILTER EXISTS statement.
    """
    coordinates = format_coordinates_as_wkt(bbox)
    srid, wkt = get_wkt_from_coords(coordinates, "Polygon", filter_crs)

    # Variables for the query
    subject = Var(value="focus_node")
    geom_bn_var = Var(
        value="geom_bnode_bbox"
    )  # Make var names unique if used alongside others
    geom_lit_var = Var(value="geom_var_bbox")

    target_system = settings.spatial_query_format
    if target_system not in ["geosparql", "qlever", "graphdb"]:
        raise NotImplementedError(
            f"Spatial query format '{target_system}' not supported for CQL."
        )

    processed_wkt = wkt
    if target_system in ["geosparql", "graphdb"]:  # For QLever, plain wkt is used
        processed_wkt = f"<{srid}> {wkt}"

    # BGP to keep outside the FILTER EXISTS
    bgp_list = []

    # Create GGPS which can be used with or without FILTER EXISTS
    ggps = GroupGraphPatternSub()
    final_gpnt = None

    if target_system == "graphdb":
        # Add geometry triples to bgp_list (outside FILTER EXISTS)
        bgp_list.extend(
            [
                TriplesSameSubjectPath.from_spo(
                    subject, IRI(value=GEO.hasGeometry), geom_bn_var
                ),
                TriplesSameSubjectPath.from_spo(
                    geom_bn_var, IRI(value=GEO.asWKT), geom_lit_var
                ),
            ]
        )
        # Add the filter predicate triple for GraphDB
        ggps.add_pattern(
            TriplesBlock(
                [
                    TriplesSameSubjectPath.from_spo(
                        geom_bn_var,
                        IRI(value=GEO.sfIntersects),
                        _wkt_literal(processed_wkt),
                    )
                ]
            )
        )
        # use a FILTER EXISTS, in most but not all cases this is more performant with the GraphDB special predicates
        final_gpnt = create_filter_exists(ggps)

    elif target_system in ["geosparql", "qlever"]:
        # Add geometry triple patterns first (inside the block)
        ggps.add_pattern(
            TriplesBlock(
                [
                    TriplesSameSubjectPath.from_spo(
                        subject, IRI(value=GEO.hasGeometry), geom_bn_var
                    )
                ]
            )
        )
        ggps.add_pattern(_bound_filter(geom_bn_var))
        ggps.add_pattern(
            TriplesBlock(
                [
                    TriplesSameSubjectPath.from_spo(
                        geom_bn_var, IRI(value=GEO.asWKT), geom_lit_var
                    )
                ]
            )
        )

        # Add spatial filter patterns after geometry triples
        spatial_filter_gpnts = generate_spatial_filter_clause(
            wkt_value=processed_wkt,
            subject_var=subject,
            geom_bnode_var=geom_bn_var,
            geom_wkt_lit_var=geom_lit_var,
            cql_operator="s_intersects",
            target_system=target_system,
        )
        if not spatial_filter_gpnts:
            raise ValueError(
                "generate_spatial_filter_clause returned no patterns for GeoSPARQL bbox."
            )

        for gpnt in spatial_filter_gpnts:
            ggps.add_pattern(gpnt)

        # do not use a FILTER EXISTS, assume the triplestore query optimiser will execute performantly
        final_gpnt = GroupOrUnionGraphPattern([GroupGraphPattern(ggps)])

    return [final_gpnt], bgp_list
