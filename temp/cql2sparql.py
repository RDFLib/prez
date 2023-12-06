from typing import Generator

from pyld import jsonld
from rdflib import URIRef, Namespace, Variable, Literal
from rdflib.namespace import GEO

from temp.grammar import (
    GroupOrUnionGraphPattern,
    GroupGraphPatternSub,
    TriplesBlock,
    SimplifiedTriple,
    GroupGraphPattern,
    GraphPatternNotTriples,
    Filter,
    InlineDataOneVar,
    InlineData,
    DataBlock,
    WhereClause,
    ConstructTemplate,
    SolutionModifier,
    ConstructQuery,
    ConstructTriples,
)
from temp.cql_sparql_reference import (
    cql_sparql_spatial_mapping,
    cql_to_shapely_mapping,
)

CQL = Namespace("http://www.opengis.net/doc/IS/cql2/1.0/")


class CQLParser:
    def __init__(self, cql=None, context: dict = None, cql_json: dict = None):
        self.ggps_inner_select = None
        self.cql = cql
        self.context = context
        self.cql_json = cql_json
        self.var_counter = 0
        self.query_object = None
        self.query_str = None
        # self.prefixes = self.extract_prefixes(self.context)

    def generate_jsonld(self):
        combined = {"@context": self.context, **self.cql}
        self.cql_json = jsonld.expand(combined, options={"base": "h"})[0]

    def extract_prefixes(self, prefix_dict: dict) -> dict:
        """
        Extracts prefixes and their URIs from the dictionary and formats them for SPARQL queries.

        :param prefix_dict: Dictionary containing prefixes and their URIs.
        :return: Dictionary containing PREFIX statements for SPARQL queries.
        """
        sparql_prefixes = {}

        # Filtering out keys that don't correspond to prefixes or are special keys
        special_keys = ["args", "op", "property", "@version"]
        for prefix, entry in prefix_dict.items():
            if prefix not in special_keys and isinstance(entry, str):
                sparql_prefixes[prefix] = URIRef(entry)
        return sparql_prefixes

    def parse(self):
        root = self.cql_json
        self.ggps_inner_select = next(self.parse_logical_operators(root))
        where = WhereClause(
            group_graph_pattern=GroupGraphPattern(content=self.ggps_inner_select)
        )
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples(triples=where.collect_triples())
        )
        solution_modifier = SolutionModifier()
        self.query_object = ConstructQuery(
            construct_template=construct_template,
            where_clause=where,
            solution_modifier=solution_modifier,
        )
        self.query_str = "".join(part for part in self.query_object.render())

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

            gougp = GroupOrUnionGraphPattern(group_graph_patterns=or_components)
            gpnt = GraphPatternNotTriples(content=gougp)
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
        simple_triple = SimplifiedTriple(
            subject=subject, predicate=predicate, object=object
        )
        if ggps.triples_block:
            ggps.triples_block.triples.append(simple_triple)
        else:
            ggps.triples_block = TriplesBlock(triples=[simple_triple])

    def _append_graph_pattern(self, ggps, graph_pattern):
        if ggps.graph_patterns_or_triples_blocks:
            ggps.graph_patterns_or_triples_blocks.append(graph_pattern)
        else:
            ggps.graph_patterns_or_triples_blocks = [graph_pattern]

    def _handle_comparison(self, operator, args, existing_ggps=None):
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        prop = args[0].get(str(CQL.property))[0].get("@id")
        inverse = False  # for inverse properties
        if prop.startswith("^"):
            prop = prop[1:]
            inverse = True
        value = args[1].get("@value")
        subject = Variable("focus_node")
        predicate = URIRef(prop)

        object = Variable(f"var_{self.var_counter}")
        if operator == "=":
            inline_data_one_var = InlineDataOneVar(
                variable=object, values=[Literal(value)]
            )
            gpnt = GraphPatternNotTriples(
                content=InlineData(data_block=DataBlock(block=inline_data_one_var))
            )
            self._append_graph_pattern(ggps, gpnt)
        else:
            filter_clause = Filter(
                variable=object, expression=operator, value=Literal(value)
            )
            self._append_graph_pattern(ggps, filter_clause)

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

        subject = Variable("focus_node")
        predicate = URIRef(prop)
        obj = Variable(f"var_{self.var_counter}")
        if inverse:
            self._add_triple(ggps, obj, predicate, subject)
        else:
            self._add_triple(ggps, subject, predicate, obj)
        filter_clause = Filter(variable=obj, expression="regex", value=Literal(value))
        self._append_graph_pattern(ggps, filter_clause)
        yield ggps

    def _handle_spatial(self, operator, args, existing_ggps=None):
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        coordinates_list = args[1].get("http://example.com/vocab/coordinates")
        coordinates, geom_type = self._extract_spatial_info(coordinates_list, args)

        if coordinates:
            wkt = cql_to_shapely_mapping[geom_type](coordinates).wkt
            subject = Variable("focus_node")
            geom_bn_var = Variable("geom_bnode")
            geom_lit_var = Variable("geom_var")
            self._add_triple(ggps, subject, GEO.hasGeometry, geom_bn_var)
            self._add_triple(ggps, geom_bn_var, GEO.asWKT, geom_lit_var)
            spatial_filter = Filter(
                variable=geom_lit_var,
                expression=cql_sparql_spatial_mapping[operator],
                value=Literal(wkt),
            )
            self._append_graph_pattern(ggps, spatial_filter)

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
        rdflib_literal_values = [Literal(value) for value in literal_values]
        rdflib_uri_values = [URIRef(value) for value in uri_values]
        all_values = rdflib_literal_values + rdflib_uri_values
        subject = Variable("focus_node")
        predicate = URIRef(prop)
        object = Variable(f"var_{self.var_counter}")
        if inverse:
            self._add_triple(ggps, object, predicate, subject)
        else:
            self._add_triple(ggps, subject, predicate, object)
        inline_data_one_var = InlineDataOneVar(variable=object, values=all_values)
        gpnt = GraphPatternNotTriples(
            content=InlineData(data_block=DataBlock(block=inline_data_one_var))
        )
        self._append_graph_pattern(ggps, gpnt)

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
