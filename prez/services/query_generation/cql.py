import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Generator

from pyld import jsonld
from rdf2geojson.contrib.geomet.util import flatten_multi_dim
from rdf2geojson.contrib.geomet.wkt import dumps
from rdflib import Namespace, URIRef
from rdflib.namespace import GEO
from sparql_grammar_pydantic import (
    IRI,
    AdditiveExpression,
    ArgList,
    BooleanLiteral,
    BrackettedExpression,
    BuiltInCall,
    ConditionalAndExpression,
    ConditionalOrExpression,
    Constraint,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    DataBlock,
    DataBlockValue,
    Expression,
    Filter,
    FunctionCall,
    GraphPatternNotTriples,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    InlineData,
    InlineDataOneVar,
    MultiplicativeExpression,
    NumericExpression,
    NumericLiteral,
    PrimaryExpression,
    RDFLiteral,
    RegexExpression,
    RelationalExpression,
    SolutionModifier,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    UnaryExpression,
    ValueLogical,
    Var,
    WhereClause, IRIOrFunction,
)

from prez.cache import prez_system_graph
from prez.models.query_params import parse_datetime
from prez.reference_data.cql.geo_function_mapping import cql_sparql_spatial_mapping
from prez.services.query_generation.shacl import PropertyShape

CQL = Namespace("http://www.opengis.net/doc/IS/cql2/1.0/")

SUPPORTED_CQL_TIME_OPERATORS = {
    "t_after",
    "t_before",
    "t_contains",
    "t_disjoint",
    "t_during",
    "t_equals",
    "t_finishedBy",
    "t_finishes",
    "t_intersects",
    "t_meets",
    "t_metBy",
    "t_overlappedBy",
    "t_overlaps",
    "t_startedBy",
    "t_starts",
}

UNBOUNDED = "unbounded"

relations_path = Path(__file__).parent.parent.parent / (
    "reference_data/cql/bounded_temporal_interval_relation_matrix" ".json"
)
relations = json.loads(relations_path.read_text())

SHACL_FILTER_NAMESPACE = Namespace("https://cql-shacl-filter/")


class CQLParser:
    def __init__(
        self,
        cql=None,
        cql_json: dict = None,
        crs=None,
        queryable_props=None,
    ):
        self.ggps_inner_select = None
        self.inner_select_gpnt_list = None
        self.inner_select_vars: list[Var] = []
        self.cql: dict = cql
        self.cql_json = cql_json
        self.var_counter = 0
        self.query_object = None
        self.query_str = None
        self.gpnt_list = []
        self.tss_list = []
        self.tssp_list = []
        self.crs = crs
        self.queryable_props = queryable_props

    def generate_jsonld(self):
        self.cql_json = self.cql

    def parse(self):
        root = self.cql_json
        self.ggps_inner_select = next(self.parse_logical_operators(root))
        where = WhereClause(
            group_graph_pattern=GroupGraphPattern(content=self.ggps_inner_select)
        )
        if self.tss_list:
            construct_triples = ConstructTriples.from_tss_list(self.tss_list)
        else:
            construct_triples = None
        construct_template = ConstructTemplate(construct_triples=construct_triples)
        solution_modifier = SolutionModifier()
        self.query_object = ConstructQuery(
            construct_template=construct_template,
            where_clause=where,
            solution_modifier=solution_modifier,
        )
        self.query_str = self.query_object.to_string()
        gpotb = self.query_object.where_clause.group_graph_pattern.content
        gpnt_list = [
            i
            for i in gpotb.graph_patterns_or_triples_blocks
            if isinstance(i, GraphPatternNotTriples)
        ]
        self.inner_select_gpnt_list = gpnt_list

    def parse_logical_operators(
        self, element, existing_ggps=None
    ) -> Generator[GroupGraphPatternSub, None, None]:
        operator = element.get("op")
        args = element.get("args")

        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        if operator == "and":
            for arg in args:
                # Process each argument and update the same ggps without yielding
                list(self.parse_logical_operators(arg, ggps))
            # If a new ggps was created (not passed from outside), yield it
            if existing_ggps is None:
                yield ggps

        elif operator == "or":
            # Collect components and then yield a GroupOrUnionGraphPattern
            # ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()
            or_components = []
            for arg in args:
                # If the result is not a GroupGraphPatternSub, wrap it.
                component = next(self.parse_logical_operators(arg), None)
                if isinstance(component, GroupGraphPatternSub):
                    component = GroupGraphPattern(content=component)
                or_components.append(component)

            gpnt = GraphPatternNotTriples(
                content=GroupOrUnionGraphPattern(group_graph_patterns=or_components)
            )
            if ggps.graph_patterns_or_triples_blocks:
                ggps.graph_patterns_or_triples_blocks.append(gpnt)
            else:
                ggps.graph_patterns_or_triples_blocks = [gpnt]
            if existing_ggps is None:
                yield ggps

        if operator in ["<", "=", ">", "<=", ">="]:
            yield from self._handle_comparison(operator, args, ggps)
        elif operator == "like":
            yield from self._handle_like(args, ggps)
        elif operator in cql_sparql_spatial_mapping:
            yield from self._handle_spatial(operator, args, ggps)
        elif operator == "in":
            yield from self._handle_in(args, ggps)
        elif operator in SUPPORTED_CQL_TIME_OPERATORS:
            yield from self._handle_temporal(operator, args, ggps)
        else:
            raise NotImplementedError(f"Operator {operator} not implemented.")

    def _add_triple(self, ggps, subject, predicate, object):
        tssp = TriplesSameSubjectPath.from_spo(
            subject=subject, predicate=predicate, object=object
        )
        tss = TriplesSameSubject.from_spo(
            subject=subject, predicate=predicate, object=object
        )
        self.tss_list.append(tss)
        self.tssp_list.append(tssp)
        if ggps.triples_block:
            ggps.triples_block = TriplesBlock(
                triples=tssp, triples_block=ggps.triples_block
            )
        else:
            ggps.triples_block = TriplesBlock(triples=tssp)

    def _handle_comparison(self, operator, args, existing_ggps=None):

        val = args[1]
        if isinstance(val, str) and val.startswith("http"):  # hack
            value = IRI(value=val)
        elif isinstance(val, (int, float)):  # literal numeric
            value = NumericLiteral(value=val)
        else:  # literal string
            value = RDFLiteral(value=val)

        if operator == "=" and isinstance(value, IRI):  # use a triple pattern match rather than FILTER
            ggps, obj = self._add_tss_tssp(args, existing_ggps, value)
        else:  # use a FILTER
            ggps, obj = self._add_tss_tssp(args, existing_ggps)
            object_pe = PrimaryExpression(content=obj)
            value_pe = PrimaryExpression(content=value)
            values_constraint = Filter.filter_relational(
                focus=object_pe, comparators=value_pe, operator=operator
            )
            gpnt = GraphPatternNotTriples(content=values_constraint)
            ggps.add_pattern(gpnt)

        yield ggps

    def _add_tss_tssp(self, args, existing_ggps, obj=None):
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()
        prop = args[0].get("property")
        if self.queryable_props and prop in self.queryable_props:
            shacl_defined_obj = self._handle_shacl_defined_prop(prop)
            if not obj:
                obj = shacl_defined_obj
        else:
            subject = Var(value="focus_node")
            predicate = IRI(value=prop)
            var_obj = Var(value=f"var_{self.var_counter}")
            if not obj:
                obj = var_obj
            self._add_triple(ggps, subject, predicate, obj)
        return ggps, obj

    def _handle_like(self, args, existing_ggps=None):
        ggps, object = self._add_tss_tssp(args, existing_ggps)

        value = args[1].replace("%", ".*").replace("_", ".").replace("\\", "\\\\")

        filter_gpnt = GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=BuiltInCall(
                        other_expressions=RegexExpression(
                            text_expression=Expression.from_primary_expression(
                                primary_expression=PrimaryExpression(content=object)
                            ),
                            pattern_expression=Expression.from_primary_expression(
                                primary_expression=PrimaryExpression(
                                    content=RDFLiteral(value=value)
                                )
                            ),
                        )
                    )
                )
            )
        )
        ggps.add_pattern(filter_gpnt)
        yield ggps

    def _handle_spatial(self, operator, args, existing_ggps=None):
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        coordinates = args[1].get("coordinates")
        geom_type = args[1].get("type")
        if args[1].get("bbox"):
            geom_type = "Polygon"

        if coordinates:
            wkt = get_wkt_from_coords(coordinates, geom_type)
            wkt_with_crs = f"<{self.crs}> {wkt}"
            prop = args[0].get("property")
            if prop == "geometry":
                subject = Var(value="focus_node")
            else:
                subject = IRI(value=prop)
            geom_bn_var = Var(value="geom_bnode")
            geom_lit_var = Var(value="geom_var")
            self._add_triple(ggps, subject, IRI(value=GEO.hasGeometry), geom_bn_var)
            self._add_triple(ggps, geom_bn_var, IRI(value=GEO.asWKT), geom_lit_var)

            geom_func_iri = IRI(value=cql_sparql_spatial_mapping[operator])
            geom_1_exp = Expression.from_primary_expression(
                primary_expression=PrimaryExpression(content=geom_lit_var)
            )
            geom_2_datatype = IRI(
                value="http://www.opengis.net/ont/geosparql#wktLiteral"
            )
            geom_2_exp = Expression.from_primary_expression(
                primary_expression=PrimaryExpression(
                    content=RDFLiteral(value=wkt_with_crs, datatype=geom_2_datatype)
                )
            )
            arg_list = ArgList(expressions=[geom_1_exp, geom_2_exp])
            fc = FunctionCall(iri=geom_func_iri, arg_list=arg_list)

            spatial_filter = Filter(constraint=Constraint(content=fc))
            filter_gpnt = GraphPatternNotTriples(content=spatial_filter)
            ggps.add_pattern(filter_gpnt)
        yield ggps

    def _handle_in(self, args, existing_ggps=None):
        ggps, object = self._add_tss_tssp(args, existing_ggps)

        uri_values = []
        literal_values = []
        numeric_values = []
        for arg in args[1]:
            if isinstance(arg, str) and arg.startswith("http"):
                uri_values.append(arg)
            elif isinstance(arg, (int, float)):
                numeric_values.append(arg)
            else:
                literal_values.append(arg)

        grammar_uri_values = [IRI(value=URIRef(value)) for value in uri_values]
        grammar_literal_values = []
        for val in literal_values:
            if isinstance(val, str):
                value = RDFLiteral(value=val)
            elif isinstance(val, (int, float)):
                value = NumericLiteral(value=val)
            grammar_literal_values.append(value)
        all_values = grammar_literal_values + grammar_uri_values

        iri_db_vals = [DataBlockValue(value=p) for p in all_values]
        ildov = InlineDataOneVar(variable=object, datablockvalues=iri_db_vals)

        gpnt = GraphPatternNotTriples(
            content=InlineData(data_block=DataBlock(block=ildov))
        )
        ggps.add_pattern(gpnt)
        yield ggps

    def _handle_shacl_defined_prop(self, prop):
        tssp_list, obj = self.queryable_id_to_tssp(self.queryable_props[prop])
        # tss_triple = (
        #     Var(value="focus_node"),
        #     IRI(value=SHACL_FILTER_NAMESPACE[prop]),
        #     object,
        # )
        # self.tss_list.append(TriplesSameSubject.from_spo(*tss_triple))
        self.tssp_list.extend(tssp_list)
        self.inner_select_vars.append(obj)
        return obj

    def _extract_spatial_info(self, coordinates_list, args):
        coordinates = []
        geom_type = None
        if coordinates_list:
            # coordinates = [
            #     [coordinates_list[i], coordinates_list[i + 1]]
            #     for i in range(0, len(coordinates_list), 2)
            # ]
            coordinates = coordinates_list
            geom_type = args[1].get("type")
        bbox_list = args[1].get("bbox")
        if bbox_list:
            geom_type = "Polygon"
            bbox_values = [item for item in bbox_list]
            coordinates = format_coordinates_as_wkt(bbox_values, coordinates)
        return coordinates, geom_type

    def _handle_temporal(self, comp_func, args, existing_ggps=None):
        """For temporal filtering within CQL JSON expressions, NOT within the temporal query parameter."""
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        if len(args) != 2:
            raise ValueError(
                f"Temporal operator {comp_func} requires exactly 2 arguments."
            )

        operands = {}
        for i, arg in enumerate(args, start=1):
            # check if the arg is an interval
            interval_list = arg.get("interval")
            if interval_list:
                for n, item in enumerate(interval_list):
                    label = "start" if n == 0 else "end"
                    if isinstance(item, dict):
                        prop = item.get("property")
                        if prop:
                            self._triple_for_time_prop(ggps, i, label, prop, operands)
                    elif isinstance(item, str):
                        self._dt_to_rdf_literal(i, item, label, operands)
                continue

            # handle instants - prop and date
            label = "instant"
            # check if the arg is a property
            prop = arg.get("property")
            if prop:
                if self.queryable_props and prop in self.queryable_props:
                    obj = self._handle_shacl_defined_prop(prop)
                    operands[f"t{i}_{label}"] = obj
                else:
                    self._triple_for_time_prop(ggps, i, label, prop, operands)
                continue

            # check if the arg is a date
            date = arg.get("date") or arg.get("datetime") or arg.get("timestamp")
            if date:
                self._dt_to_rdf_literal(i, date, label, operands)

        gpnt = self.process_temporal_function(comp_func, operands)

        ggps.add_pattern(gpnt)
        yield ggps

    def get_type_and_bound(self, operands, prefix):
        """
        Get the type label and abbreviation for a temporal operand.
        Options are "instant" with "I", or "interval" with "U" (unbounded) or "B" (bounded).
        """
        if f"{prefix}_instant" in operands:
            return "instant", "I"
        elif f"{prefix}_start" in operands or f"{prefix}_end" in operands:
            start_bound = "U" if operands.get(f"{prefix}_start") is UNBOUNDED else "B"
            end_bound = "U" if operands.get(f"{prefix}_end") is UNBOUNDED else "B"
            return "interval", start_bound + end_bound
        else:
            raise ValueError(f"Invalid operand for {prefix}")

    def process_temporal_function(self, comp_func, operands):
        t1_type, t1_bound = self.get_type_and_bound(operands, "t1")
        t2_type, t2_bound = self.get_type_and_bound(operands, "t2")

        comparison_type = f"{t1_type}_{t2_type}"

        if comparison_type not in relations[comp_func]:
            raise ValueError(
                f"The {comp_func} function is not applicable to {comparison_type} comparisons."
            )

        key = f"{t1_bound}_{t2_bound}"

        result = relations[comp_func][comparison_type].get(key)

        if result is True or result is False:
            return create_filter_bool_gpnt(result)
        elif isinstance(result, dict):
            negated = relations[comp_func].get("negated", False)
            conditions = result["conditions"]
            logic = result.get(
                "logic", "AND"
            )  # Default to AND if logic is not specified
            comparisons = [
                (operands[left], op, operands[right]) for left, op, right in conditions
            ]
            if logic == "AND":
                return create_temporal_and_gpnt(comparisons)
            elif logic == "OR" and negated:  # for t_intersects only
                return create_temporal_or_gpnt(comparisons, negated=True)
            elif logic == "OR":
                return create_temporal_or_gpnt(comparisons)
            else:
                raise ValueError(f"Unknown logic type: {logic}")
        else:
            raise ValueError(
                f"Unexpected result type for {comp_func} {comparison_type} {key}"
            )

    def _triple_for_time_prop(self, ggps, i, label, prop, operands):
        value = IRI(value=prop)
        var = Var(value=f"dt_{i}_{label}")
        operands[f"t{i}_{label}"] = var
        self._add_triple(ggps, Var(value="focus_node"), value, var)

    def _dt_to_rdf_literal(self, i, dt_str, label, operands):
        if dt_str == "..":
            operands[f"t{i}_{label}"] = UNBOUNDED
        else:
            dt, _ = parse_datetime(dt_str)
            operands[f"t{i}_{label}"] = RDFLiteral(
                value=dt.isoformat(),
                datatype=IRI(value="http://www.w3.org/2001/XMLSchema#dateTime"),
            )

    def queryable_id_to_tssp(
        self,
        queryable_uri,
    ):
        queryable_shape = prez_system_graph.cbd(URIRef(queryable_uri))
        ps = PropertyShape(
            uri=URIRef(queryable_uri),
            graph=queryable_shape,
            kind="endpoint",  # could be renamed - originally only endpoint nodeshapes filtered the nodes to be selected
            focus_node=Var(value="focus_node"),
        )
        obj_var_name = (
            ps.tssp_list[0]
            .content[1]
            .first_pair[1]
            .object_paths[0]
            .graph_node_path.varorterm_or_triplesnodepath.varorterm
        )
        return ps.tssp_list, obj_var_name


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


# def create_temporal_filter_gpnt(dt: datetime, op: str) -> GraphPatternNotTriples:
#     if op not in ["=", "<=", ">=", "<", ">"]:
#         raise ValueError(f"Invalid operator: {op}")
#     return GraphPatternNotTriples(
#         content=Filter.filter_relational(
#             focus=PrimaryExpression(
#                 content=Var(value="datetime"),
#             ),
#             comparators=PrimaryExpression(
#                 content=RDFLiteral(
#                     value=dt.isoformat(),
#                     datatype=IRI(value="http://www.w3.org/2001/XMLSchema#dateTime"),
#                 )
#             ),
#             operator=op,
#         )
#     )


def create_temporal_or_gpnt(
    comparisons: list[tuple[Var | RDFLiteral, str, Var | RDFLiteral]], negated=False
) -> GraphPatternNotTriples:
    """
    Create a FILTER with multiple conditions joined by OR (||).

    Format: FILTER ( comp1 op1 comp2 || comp3 op2 comp4 || ... )

    if negated:
    Format: FILTER (! (comp1 op1 comp2 || comp3 op2 comp4 || ...) )
    """
    _and_expressions = []
    for left_comp, op, right_comp in comparisons:
        if op not in ["=", "<=", ">=", "<", ">"]:
            raise ValueError(f"Invalid operator: {op}")
        _and_expressions.append(
            ConditionalAndExpression(
                value_logicals=[
                    ValueLogical(
                        relational_expression=RelationalExpression(
                            left=NumericExpression(
                                additive_expression=AdditiveExpression(
                                    base_expression=MultiplicativeExpression(
                                        base_expression=UnaryExpression(
                                            primary_expression=PrimaryExpression(
                                                content=left_comp
                                            )
                                        )
                                    )
                                )
                            ),
                            operator=op,
                            right=NumericExpression(
                                additive_expression=AdditiveExpression(
                                    base_expression=MultiplicativeExpression(
                                        base_expression=UnaryExpression(
                                            primary_expression=PrimaryExpression(
                                                content=right_comp
                                            )
                                        )
                                    )
                                )
                            ),
                        )
                    )
                ]
            )
        )
    if not negated:
        return GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=BrackettedExpression(
                        expression=Expression(
                            conditional_or_expression=ConditionalOrExpression(
                                conditional_and_expressions=_and_expressions
                            )
                        )
                    )
                )
            )
        )
    else:
        return GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=BrackettedExpression(
                        expression=Expression(
                            conditional_or_expression=ConditionalOrExpression(
                                conditional_and_expressions=[
                                    ConditionalAndExpression(
                                        value_logicals=[
                                            ValueLogical(
                                                relational_expression=RelationalExpression(
                                                    left=NumericExpression(
                                                        additive_expression=AdditiveExpression(
                                                            base_expression=MultiplicativeExpression(
                                                                base_expression=UnaryExpression(
                                                                    operator="!",
                                                                    primary_expression=PrimaryExpression(
                                                                        content=BrackettedExpression(
                                                                            expression=Expression(
                                                                                conditional_or_expression=ConditionalOrExpression(
                                                                                    conditional_and_expressions=_and_expressions
                                                                                )
                                                                            )
                                                                        )
                                                                    ),
                                                                )
                                                            )
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
                )
            )
        )


def create_filter_bool_gpnt(boolean: bool) -> GraphPatternNotTriples:
    """
    For filtering out all results in scenarios where the input arguments are valid but logically determine that the
    filter will filter out all results.

    generates FILTER(false) or FILTER(true)
    """
    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BrackettedExpression(
                    expression=Expression.from_primary_expression(
                        primary_expression=PrimaryExpression(
                            content=BooleanLiteral(value=boolean)
                        )
                    )
                )
            )
        )
    )


def create_temporal_and_gpnt(
    comparisons: list[tuple[Var | RDFLiteral, str, Var | RDFLiteral]]
) -> GraphPatternNotTriples:
    """
    Create a FILTER with multiple conditions joined by AND.

    :param comparisons: List of tuples, each containing (left_comp, operator, right_comp)
    :return: GraphPatternNotTriples

    Format:
    FILTER ( comp1 op1 comp2 && comp3 op2 comp4 && ... )
    """
    _vl_expressions = []

    for left_comp, op, right_comp in comparisons:
        if op not in ["=", "<=", ">=", "<", ">"]:
            raise ValueError(f"Invalid operator: {op}")

        _vl_expressions.append(
            ValueLogical(
                relational_expression=RelationalExpression(
                    left=NumericExpression(
                        additive_expression=AdditiveExpression(
                            base_expression=MultiplicativeExpression(
                                base_expression=UnaryExpression(
                                    primary_expression=PrimaryExpression(
                                        content=left_comp
                                    )
                                )
                            )
                        )
                    ),
                    operator=op,
                    right=NumericExpression(
                        additive_expression=AdditiveExpression(
                            base_expression=MultiplicativeExpression(
                                base_expression=UnaryExpression(
                                    primary_expression=PrimaryExpression(
                                        content=right_comp
                                    )
                                )
                            )
                        )
                    ),
                )
            )
        )

    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BrackettedExpression(
                    expression=Expression(
                        conditional_or_expression=ConditionalOrExpression(
                            conditional_and_expressions=[
                                ConditionalAndExpression(value_logicals=_vl_expressions)
                            ]
                        )
                    )
                )
            )
        )
    )
