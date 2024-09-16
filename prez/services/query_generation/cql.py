import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Generator

from pyld import jsonld
from rdf2geojson.contrib.geomet.util import flatten_multi_dim
from rdf2geojson.contrib.geomet.wkt import dumps
from rdflib import URIRef, Namespace
from rdflib.namespace import GEO
from sparql_grammar_pydantic import (
    ArgList,
    FunctionCall,
    ConstructQuery,
    IRI,
    Var,
    GraphPatternNotTriples,
    Expression,
    PrimaryExpression,
    BuiltInCall,
    ConstructTemplate,
    ConstructTriples,
    TriplesSameSubject,
    WhereClause,
    GroupGraphPattern,
    GroupGraphPatternSub,
    TriplesBlock,
    TriplesSameSubjectPath,
    SolutionModifier,
    GroupOrUnionGraphPattern,
    NumericLiteral,
    RegexExpression,
    InlineData,
    DataBlock,
    InlineDataOneVar,
    DataBlockValue,
    RDFLiteral,
    Filter,
    Constraint,
    ConditionalAndExpression,
    ValueLogical,
    RelationalExpression,
    NumericExpression,
    AdditiveExpression,
    MultiplicativeExpression,
    UnaryExpression,
    BrackettedExpression,
    ConditionalOrExpression,
    BooleanLiteral,
)

from prez.models.query_params import parse_datetime
from prez.reference_data.cql.geo_function_mapping import (
    cql_sparql_spatial_mapping,
)

CQL = Namespace("http://www.opengis.net/doc/IS/cql2/1.0/")

# SUPPORTED_CQL_TIME_OPERATORS = {
#     "t_after",
#     "t_before",
#     "t_equals",
#     "t_disjoint",
#     "t_intersects",
# }


# all CQL time operators
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


class CQLParser:
    def __init__(self, cql=None, context: dict = None, cql_json: dict = None, crs=None):
        self.ggps_inner_select = None
        self.inner_select_gpnt_list = None
        self.cql: dict = cql
        self.context = context
        self.cql_json = cql_json
        self.var_counter = 0
        self.query_object = None
        self.query_str = None
        self.gpnt_list = []
        self.tss_list = []
        self.tssp_list = []
        self.crs = crs

    def generate_jsonld(self):
        combined = {"@context": self.context, **self.cql}
        self.cql_json = jsonld.expand(combined, options={"base": "h"})[0]

    def parse(self):
        root = self.cql_json
        self.ggps_inner_select = next(self.parse_logical_operators(root))
        where = WhereClause(
            group_graph_pattern=GroupGraphPattern(content=self.ggps_inner_select)
        )
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(self.tss_list)
        )
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
        operator = element.get(str(CQL.operator))[0].get("@value")
        args = element.get(str(CQL.args))

        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        if operator == "and":
            and_components = []
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
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        prop = args[0].get(str(CQL.property))[0].get("@id")
        inverse = False  # for inverse properties
        if prop.startswith("^"):
            prop = prop[1:]
            inverse = True
        val = args[1].get("@value")
        if not val:  # then should be an IRI
            val = args[1].get("@id")
            value = IRI(value=val)
        elif isinstance(val, str):  # literal string
            value = RDFLiteral(value=val)
        elif isinstance(val, (int, float)):  # literal numeric
            value = NumericLiteral(value=val)
        subject = Var(value="focus_node")
        predicate = IRI(value=prop)

        object = Var(value=f"var_{self.var_counter}")
        object_pe = PrimaryExpression(content=object)
        if operator == "=":
            iri_db_vals = [DataBlockValue(value=value)]
            ildov = InlineDataOneVar(variable=object, datablockvalues=iri_db_vals)
            gpnt = GraphPatternNotTriples(
                content=InlineData(data_block=DataBlock(block=ildov))
            )
            ggps.add_pattern(gpnt)
        else:
            value_pe = PrimaryExpression(content=value)
            values_constraint = Filter.filter_relational(
                focus=object_pe, comparators=value_pe, operator=operator
            )
            gpnt = GraphPatternNotTriples(content=values_constraint)
            ggps.add_pattern(gpnt)

        if inverse:
            self._add_triple(ggps, object, predicate, subject)
        else:
            self._add_triple(ggps, subject, predicate, object)

        yield ggps

    def _handle_like(self, args, existing_ggps=None):
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()
        prop = args[0].get(str(CQL.property))[0].get("@id")
        inverse = False
        if prop.startswith("^"):
            prop = prop[1:]
            inverse = True
        value = (
            args[1]
            .get("@value")
            .replace("%", ".*")
            .replace("_", ".")
            .replace("\\", "\\\\")
        )

        subject = Var(value="focus_node")
        predicate = IRI(value=URIRef(prop))
        obj = Var(value=f"var_{self.var_counter}")
        if inverse:
            self._add_triple(ggps, obj, predicate, subject)
        else:
            self._add_triple(ggps, subject, predicate, obj)

        filter_gpnt = GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=BuiltInCall(
                        other_expressions=RegexExpression(
                            text_expression=Expression.from_primary_expression(
                                primary_expression=PrimaryExpression(content=obj)
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

        coordinates_list = args[1].get("http://example.com/vocab/coordinates")
        coordinates, geom_type = self._extract_spatial_info(coordinates_list, args)

        if coordinates:
            wkt = get_wkt_from_coords(coordinates, geom_type)
            wkt_with_crs = f"<{self.crs}> {wkt}"
            prop = args[0].get(str(CQL.property))[0].get("@id")
            if prop == "http://example.com/geometry":
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
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        prop = args[0].get(str(CQL.property))[0].get("@id")
        inverse = False
        if prop.startswith("^"):
            prop = prop[1:]
            inverse = True
        literal_values = [item["@value"] for item in args if "@value" in item]
        uri_values = [item["@id"] for item in args if "@id" in item]
        grammar_literal_values = []
        for val in literal_values:
            if isinstance(val, str):
                value = RDFLiteral(value=val)
            elif isinstance(val, (int, float)):
                value = NumericLiteral(value=val)
            grammar_literal_values.append(value)
        grammar_uri_values = [IRI(value=URIRef(value)) for value in uri_values]
        all_values = grammar_literal_values + grammar_uri_values
        subject = Var(value="focus_node")
        predicate = IRI(value=URIRef(prop))
        object = Var(value=f"var_{self.var_counter}")
        if inverse:
            self._add_triple(ggps, object, predicate, subject)
        else:
            self._add_triple(ggps, subject, predicate, object)

        iri_db_vals = [DataBlockValue(value=p) for p in all_values]
        ildov = InlineDataOneVar(variable=object, datablockvalues=iri_db_vals)

        gpnt = GraphPatternNotTriples(
            content=InlineData(data_block=DataBlock(block=ildov))
        )
        ggps.add_pattern(gpnt)
        yield ggps

    def _extract_spatial_info(self, coordinates_list, args):
        coordinates = []
        geom_type = None
        if coordinates_list:
            coordinates = [
                (coordinates_list[i]["@value"], coordinates_list[i + 1]["@value"])
                for i in range(0, len(coordinates_list), 2)
            ]
            geom_type = args[1]["http://www.opengis.net/ont/sf#type"][0]["@value"]
        bbox_list = args[1].get("http://example.com/vocab/bbox")
        if bbox_list:
            geom_type = "Polygon"
            bbox_values = [item["@value"] for item in bbox_list]
            coordinates = format_coordinates_as_wkt(bbox_values, coordinates)
        return coordinates, geom_type

    def _handle_temporal(self, comp_func, args, existing_ggps=None):
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        if len(args) != 2:
            raise ValueError(
                f"Temporal operator {comp_func} requires exactly 2 arguments."
            )

        operands = {}
        for i, arg in enumerate(args, start=1):
            # check if the arg is an interval
            interval_list = arg.get(str(CQL.interval))
            if interval_list:
                for n, item in enumerate(interval_list):
                    label = "start" if n == 0 else "end"
                    prop = item.get(str(CQL.property))
                    if prop:
                        self._triple_for_time_prop(ggps, i, label, prop, operands)
                    date_val = item.get("@value")
                    if date_val:
                        self._dt_to_rdf_literal(i, date_val, label, operands)
                continue

            # handle instants - prop and date
            label = "instant"
            # check if the arg is a property
            prop = arg.get(str(CQL.property))
            if prop:
                self._triple_for_time_prop(ggps, i, label, prop, operands)
                continue

            # check if the arg is a date
            date = (
                arg.get(str(CQL.date))
                or arg.get(str(CQL.datetime))
                or arg.get(str(CQL.timestamp))
            )
            if date:
                date_val = date[0].get("@value")
                self._dt_to_rdf_literal(i, date_val, label, operands)

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
        prop_uri = prop[0].get("@id")
        value = IRI(value=prop_uri)
        var = Var(value=f"dt_{i}_{label}")
        operands[f"t{i}_{label}"] = var
        self._add_triple(ggps, Var(value="focus_node"), value, var)

    def _handle_interval_list(self, all_args, comparator_args, interval_list):
        for item in interval_list:
            if item.get(str(CQL.property)):
                prop = item.get(str(CQL.property))[0].get("@id")
                comparator_args.append(IRI(value=prop))
            elif item.get("@value"):
                val = item.get("@value")
                # self._dt_to_rdf_literal(comparator_args, val)
                dt, _ = parse_datetime(val)
                comparator_args.append(
                    RDFLiteral(
                        value=dt.isoformat(),
                        datatype=IRI(value="http://www.w3.org/2001/XMLSchema#dateTime"),
                    )
                )
        all_args.append(comparator_args)

    def _dt_to_rdf_literal(self, i, dt_str, label, operands):
        if dt_str == "..":
            operands[f"t{i}_{label}"] = UNBOUNDED
        else:
            dt, _ = parse_datetime(dt_str)
            operands[f"t{i}_{label}"] = RDFLiteral(
                value=dt.isoformat(),
                datatype=IRI(value="http://www.w3.org/2001/XMLSchema#dateTime"),
            )


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


def create_temporal_filter_gpnt(dt: datetime, op: str) -> GraphPatternNotTriples:
    if op not in ["=", "<=", ">=", "<", ">"]:
        raise ValueError(f"Invalid operator: {op}")
    return GraphPatternNotTriples(
        content=Filter.filter_relational(
            focus=PrimaryExpression(
                content=Var(value="datetime"),
            ),
            comparators=PrimaryExpression(
                content=RDFLiteral(
                    value=dt.isoformat(),
                    datatype=IRI(value="http://www.w3.org/2001/XMLSchema#dateTime"),
                )
            ),
            operator=op,
        )
    )


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
