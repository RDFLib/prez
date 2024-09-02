from typing import Generator

from pyld import jsonld
from rdflib import URIRef, Namespace
from rdflib.namespace import GEO, SH
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
)

from prez.reference_data.cql.geo_function_mapping import (
    cql_sparql_spatial_mapping,
    cql_to_shapely_mapping,
)

CQL = Namespace("http://www.opengis.net/doc/IS/cql2/1.0/")


class CQLParser:
    def __init__(self, cql=None, context: dict = None, cql_json: dict = None):
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
        # self._append_graph_pattern(ggps, filter_expr)
        yield ggps

    def _handle_spatial(self, operator, args, existing_ggps=None):
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        coordinates_list = args[1].get("http://example.com/vocab/coordinates")
        coordinates, geom_type = self._extract_spatial_info(coordinates_list, args)

        if coordinates:
            wkt = self.get_wkt_from_coords(coordinates, geom_type)
            prop = args[0].get(str(CQL.property))[0].get("@id")
            if prop == 'http://example.com/geometry':
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
                    content=RDFLiteral(value=wkt, datatype=geom_2_datatype)
                )
            )
            arg_list = ArgList(expressions=[geom_1_exp, geom_2_exp])
            fc = FunctionCall(iri=geom_func_iri, arg_list=arg_list)

            spatial_filter = Filter(constraint=Constraint(content=fc))
            filter_gpnt = GraphPatternNotTriples(content=spatial_filter)
            ggps.add_pattern(filter_gpnt)
        yield ggps

    def get_wkt_from_coords(self, coordinates, geom_type):
        shapely_spatial_class = cql_to_shapely_mapping.get(geom_type)
        if not shapely_spatial_class:
            raise NotImplementedError(
                f'Geometry Class for "{geom_type}" not found in Shapely.'
            )
        wkt = shapely_spatial_class(coordinates).wkt
        return wkt

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
        # self._append_graph_pattern(ggps, gpnt)
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
            if len(bbox_values) == 4:
                coordinates = [
                    (bbox_values[0], bbox_values[1]),
                    (bbox_values[0], bbox_values[3]),
                    (bbox_values[2], bbox_values[3]),
                    (bbox_values[2], bbox_values[1]),
                    (bbox_values[0], bbox_values[1]),
                ]
        return coordinates, geom_type
