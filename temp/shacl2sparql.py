import json
from pathlib import Path
from string import Template
from typing import Union, Optional

from rdflib import URIRef, Variable, Namespace, Graph, SH, RDF, BNode, Literal
from rdflib.collection import Collection

from temp.grammar import (
    TriplesBlock,
    OptionalGraphPattern,
    SolutionModifier,
    GroupGraphPattern,
    SimplifiedTriple,
    SubSelect,
    SubSelectString,
    GroupOrUnionGraphPattern,
    GroupGraphPatternSub,
    GraphPatternNotTriples,
    SelectClause,
    WhereClause,
    LimitClause,
    OffsetClause,
    LimitOffsetClauses,
    InlineDataOneVar,
    DataBlock,
    InlineData,
    ConstructTemplate,
    ConstructTriples,
    ConstructQuery,
    Filter,
)

ONT = Namespace("https://prez.dev/ont/")
ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
SHEXT = Namespace("http://example.com/shacl-extension#")


class SHACLParser:
    def __init__(
        self,
        runtime_values: dict,
        endpoint_graph: Graph,
        profile_graph: Graph,
        endpoint_uri: Optional[URIRef] = None,
        profile_uri: Optional[URIRef] = None,
        additional_ggps: Optional[GroupGraphPatternSub] = None,
    ):
        self.runtime_values = runtime_values
        self.endpoint_graph: Graph = endpoint_graph
        self.profile_graph: Graph = profile_graph
        self.endpoint_uri: Optional[URIRef] = endpoint_uri
        self.profile_uri: Optional[URIRef] = profile_uri
        self.additional_ggps: Optional[GroupGraphPatternSub] = additional_ggps

        self.focus_node: Union[URIRef, Variable] = Variable("focus_node")

        self.sparql = None
        self.results = None

        self.construct_triples = None
        self.main_where_ggps = GroupGraphPatternSub()
        self.sub_select_ggps = None
        self.optional_patterns = None
        self.where_patterns = None

        self.default_limit = None
        self.default_offset = None

        self.runtime_vals_expanded = None
        self.merged_runtime_and_default_vals = None
        self._expand_runtime_vars()
        self._merge_runtime_and_default_vars()

    def _expand_runtime_vars(self):
        self.runtime_vals_expanded = {}
        for k, v in self.runtime_values.items():
            if k in ["limit", "offset"]:
                self.runtime_vals_expanded[k] = v
            elif v:
                self.runtime_vals_expanded[k] = URIRef(v).n3()

    def _merge_runtime_and_default_vars(self):
        default_args = {"limit": self.default_limit, "offset": self.default_offset}
        self.merged_runtime_and_default_vals = default_args | self.runtime_vals_expanded

    def generate_sparql(self):
        """
        Generates SPARQL query from SHACL profile_graph.
        """
        self.parse_endpoint_definition()
        self.parse_profile()
        self._generate_query()

    def _generate_query(self):
        where = WhereClause(
            group_graph_pattern=GroupGraphPattern(content=self.main_where_ggps)
        )
        if self.construct_triples:
            self.construct_triples.extend(where.collect_triples())
        else:
            self.construct_triples = where.collect_triples()
        self.construct_triples = list(set(self.construct_triples))
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples(triples=self.construct_triples)
        )
        solution_modifier = SolutionModifier()
        query = ConstructQuery(
            construct_template=construct_template,
            where_clause=where,
            solution_modifier=solution_modifier,
        )
        query_str = "".join(part for part in query.render())
        self.sparql = query_str

    def parse_endpoint_definition(self):
        """
        Either set the focus_node to a URIRef, if a target node is provided, or generate a triple pattern to get list items
        Generates triples for the endpoint definition with runtime values substituted.
        """
        # sparql targets
        target_bn = list(
            self.endpoint_graph.objects(subject=self.endpoint_uri, predicate=SH.target)
        )
        target_nodes = list(
            self.endpoint_graph.objects(
                subject=self.endpoint_uri, predicate=SH.targetNode
            )
        )
        target_classes = list(
            self.endpoint_graph.objects(
                subject=self.endpoint_uri, predicate=SH.targetClass
            )
        )
        rule_nodes = list(
            self.endpoint_graph.objects(subject=self.endpoint_uri, predicate=SH.rule)
        )

        # objects - just set the focus node.
        if target_nodes:
            target_node_var = str(target_nodes[0])
            target_node_val = target_node_var[1:]
            target_uri = URIRef(self.runtime_values[target_node_val])
            self.focus_node = target_uri

        # rule nodes - for CONSTRUCT TRIPLES patterns.
        if rule_nodes:
            for rule_node in rule_nodes:
                self._create_construct_triples_from_sh_rules(rule_node)

        # if it's a listing endpoint, get limit and offset if available, otherwise use defaults.
        endpoint_type = self.get_endpoint_type()
        if endpoint_type == ONT.ListingEndpoint:
            # default limit and offset
            self._set_default_limit_and_offset()
        self._merge_runtime_and_default_vars()

        # sh:target / sh:select
        if target_bn:
            ggp = self.create_select_subquery_from_template(target_bn)
            self._add_target_class(target_classes[0])
            self._add_ggp_to_main_ggps(ggp)

        # don't use the target class if there's a sh:target / sh:select #TODO confirm why this caused issues - duplicate
        #  pattern matches in the subquery?
        elif target_classes:
            if (
                endpoint_type == ONT.ListingEndpoint
            ):  # ignore class for non listing at present
                ggp = self.create_select_subquery_for_class_listing(target_classes)
                self._add_ggp_to_main_ggps(ggp)

    def _add_ggp_to_main_ggps(self, ggp):
        gorugp = GroupOrUnionGraphPattern(group_graph_patterns=[ggp])
        gpnt = GraphPatternNotTriples(content=gorugp)
        self.main_where_ggps.add_pattern(gpnt)

    def _create_construct_triples_from_sh_rules(self, rule_node):
        subject = self.endpoint_graph.value(subject=rule_node, predicate=SH.subject)
        predicate = self.endpoint_graph.value(subject=rule_node, predicate=SH.predicate)
        object = self.endpoint_graph.value(subject=rule_node, predicate=SH.object)
        if subject == SH.this:
            subject = self.focus_node
        if isinstance(object, Literal):  # assume it's a variable of the form ?xyz
            object = Variable(str(object)[1:])
        triple = SimplifiedTriple(subject=subject, predicate=predicate, object=object)
        if self.construct_triples:
            self.construct_triples.append(triple)
        else:
            self.construct_triples = [triple]

    def create_select_subquery_for_class_listing(self, target_classes):
        target_class_var = URIRef(target_classes[0])
        triples_block = TriplesBlock(
            triples=[
                SimplifiedTriple(
                    subject=self.focus_node, predicate=RDF.type, object=target_class_var
                )
            ]
        )
        if self.additional_ggps:  # for example from cql
            ggps = GroupGraphPatternSub(
                # triples_block=triples_block,  # triples block from SHACL profile
                graph_patterns_or_triples_blocks=[
                    GraphPatternNotTriples(
                        content=GroupOrUnionGraphPattern(
                            group_graph_patterns=[
                                GroupGraphPattern(content=self.additional_ggps)
                            ]
                        )
                    )
                ]
            )
        else:
            ggps = GroupGraphPatternSub(triples_block=triples_block)
        ggp = GroupGraphPattern(content=ggps)
        sub_select_where = WhereClause(group_graph_pattern=ggp)
        select_clause = SelectClause(variables_or_all="*")
        limit = self.merged_runtime_and_default_vals["limit"]
        offset = self.merged_runtime_and_default_vals["offset"]
        if limit is not None and offset is not None:  # int = 0 is boolean False
            limit_clause = LimitClause(limit=limit)
            offset_clause = OffsetClause(offset=offset)
            limit_offset_clauses = LimitOffsetClauses(
                limit_clause=limit_clause, offset_clause=offset_clause
            )
            solution_modifier = SolutionModifier(limit_offset=limit_offset_clauses)
        else:
            solution_modifier = SolutionModifier()
        ss = SubSelect(
            select_clause=select_clause,
            where_clause=sub_select_where,
            solution_modifier=solution_modifier,
        )
        ggp = GroupGraphPattern(content=ss)
        return ggp

    def create_select_subquery_from_template(self, target_bn):
        select_statement = Template(
            str(self.endpoint_graph.value(target_bn[0], SH.select, default=None))
        )
        # expand any prefixes etc. in case the prefixes are not defined in the query this subquery is being inserted
        # into. NB SHACL does provide a mechanism to declare prefixes used in SPARQL targets - this has not been
        # implemented
        substituted_query = select_statement.substitute(
            self.merged_runtime_and_default_vals
        )
        sss = SubSelectString(select_string=substituted_query)
        ggp = GroupGraphPattern(content=sss)
        return ggp

    def _set_default_limit_and_offset(self):
        default_limit = list(
            self.endpoint_graph.objects(
                subject=self.endpoint_uri, predicate=ONT["defaultLimit"]
            )
        )
        default_offset = list(
            self.endpoint_graph.objects(
                subject=self.endpoint_uri, predicate=ONT["defaultOffset"]
            )
        )
        if not default_limit or not default_offset:
            raise ValueError(
                "Listing endpoint must have both a default limit and a default offset"
            )
        self.default_limit = int(default_limit[0])
        self.default_offset = int(default_offset[0])

    def get_endpoint_type(self):
        endpoint_type = list(
            self.endpoint_graph.objects(subject=self.endpoint_uri, predicate=RDF.type)
        )
        if not endpoint_type:
            raise ValueError(
                'Endpoint definition must have a type of either "https://prez.dev/ont/ListingEndpoint" '
                'or "https://prez.dev/ont/ObjectEndpoint"'
            )
        endpoint_type = endpoint_type[0]
        return endpoint_type

    def parse_profile(self):
        for i, property_node in enumerate(
            self.profile_graph.objects(subject=self.profile_uri, predicate=SH.property)
        ):
            self._parse_property_shapes(property_node, i)
        self._build_bnode_blocks()

    def _add_target_class(self, target_class):
        triples = [
            SimplifiedTriple(
                subject=self.focus_node, predicate=RDF.type, object=target_class
            )
        ]
        if self.construct_triples:
            self.construct_triples.extend(triples)
        else:
            self.construct_triples = triples

    def _build_bnode_blocks(self):
        bnode_depth = list(self.profile_graph.objects(subject=self.profile_uri, predicate=SHEXT["bnode-depth"]))
        if not bnode_depth or bnode_depth == [0]:
            return
        else:
            bnode_depth = int(bnode_depth[0])
        p1 = Variable(f"?bn_p_1")
        o1 = Variable(f"?bn_o_1")
        p2 = Variable(f"?bn_p_2")
        o2 = Variable(f"?bn_o_2")
        triples_block = TriplesBlock(
            triples=[
                SimplifiedTriple(subject=self.focus_node, predicate=p1, object=o1),
                SimplifiedTriple(subject=o1, predicate=p2, object=o2),
            ]
        )
        filter_block = Filter(variable=o1, expression="ISBLANK")
        gpnt = GraphPatternNotTriples(content=filter_block)
        ggps = GroupGraphPatternSub(
            triples_block=triples_block, graph_patterns_or_triples_blocks=[gpnt]
        )
        ggp = GroupGraphPattern(content=ggps)
        outer_opt = OptionalGraphPattern(group_graph_pattern=ggp)
        container_gpnt = GraphPatternNotTriples(content=outer_opt)
        container_ggps = GroupGraphPatternSub(
            graph_patterns_or_triples_blocks=[container_gpnt]
        )
        container_ggp = GroupGraphPattern(content=container_ggps)

        def process_bn_level(depth, max_depth, outer_ggps):
            old_o_var = Variable(f"?bn_o_{depth}")
            new_p_var = Variable(f"?bn_p_{depth + 1}")
            new_o_var = Variable(f"?bn_o_{depth + 1}")
            triples_block = TriplesBlock(
                triples=[
                    SimplifiedTriple(
                        subject=old_o_var, predicate=new_p_var, object=new_o_var
                    )
                ]
            )
            filter_block = Filter(variable=old_o_var, expression="ISBLANK")
            gpnt = GraphPatternNotTriples(content=filter_block)
            ggps = GroupGraphPatternSub(
                triples_block=triples_block, graph_patterns_or_triples_blocks=[gpnt]
            )
            ggp = GroupGraphPattern(content=ggps)
            opt = OptionalGraphPattern(group_graph_pattern=ggp)
            outer_ggps.graph_patterns_or_triples_blocks.append(opt)
            if depth < max_depth:
                process_bn_level(depth + 1, max_depth, ggps)

        if bnode_depth > 1:
            process_bn_level(depth=2, max_depth=bnode_depth, outer_ggps=ggps)
        self._add_ggp_to_main_ggps(container_ggp)

    def _parse_property_shapes(self, property_node, i):
        def process_path_object(path_object):
            # if path_object == SHEXT.allPredicateValues:
            #     predicates.append(Variable("preds"))
            if isinstance(path_object, BNode):
                predicate_objects_gen = self.profile_graph.predicate_objects(
                    subject=path_object
                )
                bnode_pred, bnode_obj = next(predicate_objects_gen, (None, None))
                if bnode_obj == SH.union:
                    pass
                elif bnode_pred == SH.inversePath:
                    inverse_preds.append(bnode_obj)
                elif bnode_pred == SH.alternativePath:
                    predicates.extend(list(Collection(self.profile_graph, bnode_obj)))
                else:  # "regular" paths - no special predicate, just list members
                    predicates.append(
                        tuple(Collection(self.profile_graph, path_object))
                    )
            else:  # a plain path specification to restrict the predicate to a specific value
                predicates.append(path_object)

        inverse_preds = []
        predicates = []
        union_items = None
        path_object = self.profile_graph.value(
            subject=property_node, predicate=SH.path, default=None
        )
        if isinstance(path_object, BNode):
            predicate_objects_gen = self.profile_graph.predicate_objects(
                subject=path_object
            )
            bnode_pred, bnode_obj = next(predicate_objects_gen, (None, None))
            if bnode_obj == SH.union:
                union_list_bnode = list(Collection(self.profile_graph, path_object))[1]
                union_items = list(Collection(self.profile_graph, union_list_bnode))

        ggp_list = []
        if union_items:
            for item in union_items:
                process_path_object(item)
        else:
            process_path_object(path_object)

        if inverse_preds:
            ggps_under_under_union = GroupGraphPatternSub()
            ggps = ggps_under_under_union
            ggp = GroupGraphPattern(content=ggps_under_under_union)
            ggp_list.append(ggp)
            self._add_inverse_preds(ggps, inverse_preds, i)
        if predicates:
            self._add_predicate_constraints(predicates, property_node, ggp_list)
        self._add_object_constrains(ggp_list, property_node)
        union = GroupOrUnionGraphPattern(group_graph_patterns=ggp_list)
        gpnt = GraphPatternNotTriples(content=union)

        min = int(
            self.profile_graph.value(
                subject=property_node, predicate=SH.minCount, default=1
            )
        )
        if min == 0:  # Add Optional GroupGraphPatternSub "wrapper" as the main GGPS
            ggps_under_optional = GroupGraphPatternSub(
                graph_patterns_or_triples_blocks=[gpnt]
            )
            ggp = GroupGraphPattern(content=ggps_under_optional)
            optional = OptionalGraphPattern(group_graph_pattern=ggp)
            gpnt = GraphPatternNotTriples(content=optional)
        self.main_where_ggps.add_pattern(gpnt)

    def _add_inverse_preds(self, ggps, inverse_preds, i):
        if inverse_preds:
            ggps.add_triple(
                SimplifiedTriple(
                    subject=Variable(f"inv_path_{i}"),
                    predicate=Variable(f"inv_pred_{i}"),
                    object=self.focus_node,
                )
            )
            inline_data_one_var = InlineDataOneVar(
                variable=Variable(f"inv_pred_{i}"), values=inverse_preds
            )
            data_block = DataBlock(block=inline_data_one_var)
            inline_data = InlineData(data_block=data_block)
            gpnt = GraphPatternNotTriples(content=inline_data)
            # ggps_sub = GroupGraphPatternSub(graph_patterns_or_triples_blocks=[gpnt])
            ggps.add_pattern(gpnt)

    def _add_predicate_constraints(self, predicates, property_node, ggp_list):
        # check for any sequence paths - process separately
        sps = [p for p in predicates if isinstance(p, tuple)]
        predicates = [p for p in predicates if not isinstance(p, tuple)]

        for i, (pred1, pred2) in enumerate(sps):
            t1 = SimplifiedTriple(
                subject=self.focus_node,
                predicate=pred1,
                object=Variable(f"seq_obj_{i + 1}"),
            )
            t2 = SimplifiedTriple(
                subject=Variable(f"seq_obj_{i + 1}"),
                predicate=pred2,
                object=Variable(f"seq_obj_terminal{i + 1}"),
            )
            tb = TriplesBlock(triples=[t1, t2])
            ggps = GroupGraphPatternSub(triples_block=tb)
            ggp = GroupGraphPattern(content=ggps)
            ggp_list.append(ggp)

        # process direct path predicates
        max = self.profile_graph.value(subject=property_node, predicate=SH.maxCount)
        simplified_triple = SimplifiedTriple(
            subject=self.focus_node,
            predicate=Variable("preds"),
            object=Variable("objs"),
        )
        tb = TriplesBlock(triples=[simplified_triple])
        if predicates:
            # filters must be added to all union statements
            if max == Literal(0):
                values_constraint = Filter(variable=Variable("preds"), expression="NOT IN", value=predicates)
                gpnt = GraphPatternNotTriples(content=values_constraint)
                if ggp_list:
                    for ggp in ggp_list:
                        ggp.content.add_pattern(gpnt)
                else:
                    ggps = GroupGraphPatternSub(graph_patterns_or_triples_blocks=[gpnt, tb])
                    ggp = GroupGraphPattern(content=ggps)
                    ggp_list.append(ggp)
            elif SHEXT.allPredicateValues not in predicates:  # add VALUES clause
                inline_data_one_var = InlineDataOneVar(
                    variable=Variable("preds"), values=predicates
                )
                data_block = DataBlock(block=inline_data_one_var)
                inline_data = InlineData(data_block=data_block)
                gpnt = GraphPatternNotTriples(content=inline_data)
                ggps = GroupGraphPatternSub(graph_patterns_or_triples_blocks=[gpnt, tb])
                ggp = GroupGraphPattern(content=ggps)
                ggp_list.append(ggp)
            elif predicates == [SHEXT.allPredicateValues]:
                ggps = GroupGraphPatternSub(triples_block=tb)
                ggp = GroupGraphPattern(content=ggps)
                ggp_list.append(ggp)


    def _add_object_constrains(self, ggp_list, property_node):
        value = self.profile_graph.value(
            subject=property_node, predicate=SH.hasValue, default=None
        )
        values_bn = self.profile_graph.value(
            subject=property_node, predicate=SH["in"], default=None
        )
        if value:  # a specific value
            objects = [value]
        elif values_bn:  # a set of values
            c = Collection(self.profile_graph, values_bn)
            objects = list(c)
        if value or values_bn:
            ggps = GroupGraphPatternSub()
            ggp = GroupGraphPattern(content=ggps)
            ggp_list.append(ggp)
            inline_data_one_var = InlineDataOneVar(
                variable=Variable("objs"), values=objects
            )
            data_block = DataBlock(block=inline_data_one_var)
            inline_data = InlineData(data_block=data_block)
            gpnt = GraphPatternNotTriples(content=inline_data)
            ggps.add_pattern(gpnt)
