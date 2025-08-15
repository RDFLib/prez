import json
from pathlib import Path
from typing import Generator, Literal

from rdflib import Namespace, URIRef
from rdflib.namespace import GEO
from sparql_grammar_pydantic import (
    IRI,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    GraphPatternNotTriples,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    IRIOrFunction,
    RDFLiteral,
    SolutionModifier,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)

from prez.cache import prez_system_graph
from prez.config import settings
from prez.models.query_params import parse_datetime
from prez.reference_data.cql.geo_function_mapping import (
    cql_sparql_spatial_mapping,
    cql_graphdb_spatial_properties,
)
from prez.services.query_generation.spatial_filter import (
    generate_spatial_filter_clause,
    get_wkt_from_coords,
)
from prez.services.query_generation.shacl import PropertyShape
from prez.services.query_generation.grammar_helpers import (
    convert_value_to_rdf_term,
    create_regex_filter,
    create_relational_filter,
    create_values_constraint,
    create_temporal_or_gpnt,
    create_filter_bool_gpnt,
    create_temporal_and_gpnt,
)

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
    "reference_data/cql/bounded_temporal_interval_relation_matrix.json"
)
relations = json.loads(relations_path.read_text())

SHACL_FILTER_NAMESPACE = Namespace("https://cql-shacl-filter/")


class CQLParser:
    def __init__(
        self,
        cql_json: dict | None = None,
        crs: str | None = None,
        queryable_props: dict[str, str] | None = None,
    ):
        self.inner_select_gpntotb_list: list[GraphPatternNotTriples] = []
        # Always include at least ?focus_node SELECT var
        self.inner_select_vars: list[Var] = [Var(value="focus_node")]
        self.cql_json: dict | None = cql_json
        self.var_counter: int = 0
        self.query_object: ConstructQuery | None = None
        self.query_str: str | None = None
        self.tss_list: list[TriplesSameSubject] = []
        self.tssp_list: list[TriplesSameSubjectPath] = []
        self.crs: str | None = crs
        self.queryable_props: dict[str, str] | None = queryable_props

    def parse(self):
        root = self.cql_json
        where = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=next(self.parse_logical_operators(root))
            )
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
        if gpotb.graph_patterns_or_triples_blocks:
            self.inner_select_gpntotb_list = gpotb.graph_patterns_or_triples_blocks

    def parse_logical_operators(
        self, element: dict, existing_ggps: GroupGraphPatternSub | None = None
    ) -> Generator[GroupGraphPatternSub, None, None]:
        operator = element.get("op")
        args = element.get("args")

        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        if operator == "and":
            yield from self._handle_and_operator(args, ggps, existing_ggps)
        elif operator == "or":
            yield from self._handle_or_operator(args, ggps, existing_ggps)

        # ... other operators like "<", "=", ">", "like", spatial, "in", temporal ...
        elif operator in ["<", "=", ">", "<=", ">=", "<>"]:
            if operator == "<>":
                operator = "!="  # CQL -> SPARQL equivalent
            self._handle_comparison(operator, args, ggps)
            if existing_ggps is None:
                yield ggps
        elif operator == "like":
            self._handle_like(args, ggps)
            if existing_ggps is None:
                yield ggps
        elif operator in cql_sparql_spatial_mapping:
            self._handle_spatial(operator, args, ggps)
            if existing_ggps is None:
                yield ggps
        elif operator == "in":
            self._handle_in(args, ggps)
            if existing_ggps is None:
                yield ggps
        elif operator in SUPPORTED_CQL_TIME_OPERATORS:
            self._handle_temporal(operator, args, ggps)
            if existing_ggps is None:
                yield ggps
        else:
            # This else is reached if operator is not 'and', 'or', or any of the handled elementary operators.
            raise NotImplementedError(f"Operator {operator} not implemented.")

    def _handle_and_operator(
        self,
        args: list[dict],
        ggps: GroupGraphPatternSub,
        existing_ggps: GroupGraphPatternSub | None,
    ) -> Generator[GroupGraphPatternSub, None, None]:
        """Handle AND logical operator."""
        for arg in args:
            # Process each argument and update the same ggps without yielding
            list(self.parse_logical_operators(arg, ggps))
        # If a new ggps was created (not passed from outside), yield it
        if existing_ggps is None:
            yield ggps

    def _handle_or_operator(
        self,
        args: list[dict],
        ggps: GroupGraphPatternSub,
        existing_ggps: GroupGraphPatternSub | None,
    ) -> Generator[GroupGraphPatternSub, None, None]:
        """Handle OR logical operator."""
        try:
            or_components = []
            for arg in args:
                # Recursive call for "or" branch arguments
                # existing_ggps is intentionally not passed to create a new scope for the component
                component = next(self.parse_logical_operators(arg), None)
                if isinstance(component, GroupGraphPatternSub):
                    component = GroupGraphPattern(content=component)
                or_components.append(component)

            # This GPNT represents the "{A} UNION {B}" structure
            or_expression_as_gpnt = GraphPatternNotTriples(
                content=GroupOrUnionGraphPattern(group_graph_patterns=or_components)
            )

            # 'ggps' here is the context we are adding to.
            # If existing_ggps was passed (not None), then ggps is existing_ggps (e.g. the AND's GGPS).
            # If existing_ggps was None, ggps is a new GGPS created for this current OR call.

            if existing_ggps is not None:
                # This OR is nested (e.g., inside an AND).
                # Wrap its GPNT (which is the GroupOrUnionGraphPattern) in a GGP
                # to make it an explicit { {A} UNION {B} } block in the outer scope.
                item_for_gpntotb_list = GraphPatternNotTriples(
                    content=GroupOrUnionGraphPattern(
                        group_graph_patterns=[
                            GroupGraphPattern(
                                content=GroupGraphPatternSub(
                                    graph_patterns_or_triples_blocks=[
                                        or_expression_as_gpnt
                                    ]
                                )
                            )
                        ]
                    )
                )
            else:
                # This OR is top-level for this recursive call. Its GPNT is the pattern.
                # The calling 'parse()' method will wrap the final GGPS in a GGP for the WHERE clause.
                item_for_gpntotb_list = or_expression_as_gpnt

            if ggps.graph_patterns_or_triples_blocks:
                ggps.graph_patterns_or_triples_blocks.append(item_for_gpntotb_list)
            else:
                ggps.graph_patterns_or_triples_blocks = [item_for_gpntotb_list]

        finally:
            pass  # Cleanup if needed

        if (
            existing_ggps is None
        ):  # If this OR was top-level for this call and created its own ggps
            yield ggps

    def _add_triple(
        self,
        ggps: GroupGraphPatternSub,
        subject: Var | IRI,
        predicate: IRI,
        obj: Var | IRI | RDFLiteral,
        to: Literal["tss_and_tssp", "tss", "tssp"] = "tss_and_tssp",
    ) -> None:
        if to in ["tss_and_tssp", "tss"]:
            tss = TriplesSameSubject.from_spo(
                subject=subject, predicate=predicate, object=obj
            )
            self.tss_list.append(tss)

        if to in ["tss_and_tssp", "tssp"]:
            tssp = TriplesSameSubjectPath.from_spo(
                subject=subject, predicate=predicate, object=obj
            )
            # Note: tssp goes to ggps.graph_patterns_or_triples_blocks, NOT self.tssp_list

            new_tb_for_this_tssp = TriplesBlock(triples=tssp)

            if not ggps.graph_patterns_or_triples_blocks:
                ggps.graph_patterns_or_triples_blocks = [new_tb_for_this_tssp]
            else:
                # Find if there's already a TriplesBlock to nest under the new one
                existing_tb = None
                existing_tb_index = None

                for i, gpnt_or_tb in enumerate(ggps.graph_patterns_or_triples_blocks):
                    if isinstance(gpnt_or_tb, TriplesBlock):
                        existing_tb = gpnt_or_tb
                        existing_tb_index = i
                        break

                if existing_tb:
                    # Create new TriplesBlock with current tssp and nest the existing one
                    nested_tb = TriplesBlock(triples=tssp, triples_block=existing_tb)
                    # Replace the existing TriplesBlock with the new nested one
                    ggps.graph_patterns_or_triples_blocks[existing_tb_index] = nested_tb
                else:
                    # No existing TriplesBlock, just append the new one
                    ggps.graph_patterns_or_triples_blocks.append(new_tb_for_this_tssp)

            # All patterns are channeled into the graph_patterns_or_triples_blocks list.

    def _handle_comparison(
        self,
        operator: str,
        args: list[dict],
        existing_ggps: GroupGraphPatternSub | None = None,
    ) -> None:
        value = convert_value_to_rdf_term(args[1])

        use_filter_statement = True
        if operator == "=" and isinstance(value, IRI):
            prop = args[0].get("property")
            if self.queryable_props and prop in self.queryable_props:
                # the shacl paths can be complicated, so we just get back a var and then use filter
                value = IRIOrFunction(iri=value)
                use_filter_statement = True
            else:  # non shacl - use a triple pattern match rather than FILTER
                use_filter_statement = False
                ggps, obj = self._add_tss_tssp(args, existing_ggps, value)

        if use_filter_statement:  # use a FILTER
            ggps, obj = self._add_tss_tssp(args, existing_ggps)
            filter_gpnt = create_relational_filter(obj, operator, value)
            ggps.add_pattern(filter_gpnt)

    def _add_tss_tssp(
        self,
        args: list[dict],
        existing_ggps: GroupGraphPatternSub | None,
        obj: Var | IRI | RDFLiteral | None = None,
    ) -> tuple[GroupGraphPatternSub, Var | IRI | RDFLiteral]:
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
            self._add_triple(ggps, subject, predicate, obj, "tss_and_tssp")
        return ggps, obj

    def _handle_like(
        self, args: list[dict], existing_ggps: GroupGraphPatternSub | None = None
    ) -> None:
        ggps, obj = self._add_tss_tssp(args, existing_ggps)

        pattern = args[1].replace("%", ".*").replace("_", ".").replace("\\", "\\\\")
        filter_gpnt = create_regex_filter(obj, pattern)
        ggps.add_pattern(filter_gpnt)

    def _handle_spatial(
        self,
        operator: str,
        args: list[dict],
        existing_ggps: GroupGraphPatternSub | None = None,
    ) -> None:
        self.var_counter += 1
        ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()

        coordinates = args[1].get("coordinates")
        geom_type = args[1].get("type")
        if args[1].get("bbox"):
            geom_type = "Polygon"

        if coordinates:
            srid, wkt = get_wkt_from_coords(coordinates, geom_type, self.crs)
            prop = args[0].get("property")
            if prop == "geometry":
                subject = Var(value="focus_node")
            else:
                subject = IRI(value=prop)
            geom_bn_var = Var(value="geom_bnode")
            geom_lit_var = Var(value="geom_var")

            self._add_triple(
                ggps, subject, IRI(value=GEO.hasGeometry), geom_bn_var, "tss_and_tssp"
            )
            self._add_triple(
                ggps, geom_bn_var, IRI(value=GEO.asWKT), geom_lit_var, "tss_and_tssp"
            )

            target_system = settings.spatial_query_format
            if target_system not in ["geosparql", "qlever", "graphdb"]:
                raise NotImplementedError(
                    f"Spatial query format '{target_system}' not supported for CQL."
                )

            # Prepare WKT string based on target system and CRS presence
            processed_wkt = wkt
            if target_system in [
                "geosparql",
                "graphdb",
            ]:  # For QLever, plain wkt is used
                processed_wkt = f"<{srid}> {wkt}"

            if target_system == "graphdb":
                if operator not in cql_graphdb_spatial_properties:
                    raise NotImplementedError(
                        f"CQL operator {operator} not supported for GraphDB target"
                    )
                predicate_iri = IRI(value=str(cql_graphdb_spatial_properties[operator]))
                object_wkt_literal = RDFLiteral(
                    value=processed_wkt,  # Use centrally processed WKT
                    datatype=IRI(value=str(GEO.wktLiteral)),
                )
                self._add_triple(
                    ggps, subject, predicate_iri, object_wkt_literal, to="tssp"
                )
            else:
                filter_gpnt_list = generate_spatial_filter_clause(
                    wkt_value=processed_wkt,
                    subject_var=subject,
                    geom_bnode_var=geom_bn_var,
                    geom_wkt_lit_var=geom_lit_var,
                    cql_operator=operator,
                    target_system=target_system,
                )
                for gpnt_item in filter_gpnt_list:
                    ggps.add_pattern(gpnt_item)

    def _handle_in(
        self, args: list[dict], existing_ggps: GroupGraphPatternSub | None = None
    ) -> None:
        ggps, obj = self._add_tss_tssp(args, existing_ggps)

        values_constraint = create_values_constraint(obj, args[1])
        ggps.add_pattern(values_constraint)

    def _handle_shacl_defined_prop(self, prop):
        tssp_list, obj_var = self.queryable_id_to_tssp(self.queryable_props[prop])
        self.tssp_list.extend(tssp_list)
        self.inner_select_vars.append(obj_var)
        return obj_var

    def _handle_temporal(
        self,
        comp_func: str,
        args: list[dict],
        existing_ggps: GroupGraphPatternSub | None = None,
    ) -> None:
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

    @staticmethod
    def get_type_and_bound(operands: dict, prefix: str) -> tuple[str, str]:
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
        self._add_triple(ggps, Var(value="focus_node"), value, var, "tss_and_tssp")

    @staticmethod
    def _dt_to_rdf_literal(i: int, dt_str: str, label: str, operands: dict) -> None:
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
        queryable_uri: str,
    ) -> tuple[list[TriplesSameSubjectPath], Var]:
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
