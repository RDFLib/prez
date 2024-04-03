import re
from string import Template
from typing import Union, Optional, List, Dict

from pydantic import BaseModel
from rdflib import URIRef, Namespace, Graph, SH, BNode, Literal
from rdflib.collection import Collection

from prez.cache import profiles_graph_cache, endpoints_graph_cache
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.search import SearchQueryRegex
from prez.services.query_generation.shacl import NodeShape
from temp.grammar import *

ONT = Namespace("https://prez.dev/ont/")
ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
SHEXT = Namespace("http://example.com/shacl-extension#")


# class PrezQueryConstructor(BaseModel):
#     class Config:
#         arbitrary_types_allowed = True
#
#     runtime_values: dict
#     endpoint_graph: Graph
#     profile_graph: Graph
#     listing_or_object: str
#     focus_node: Union[IRI, Var] = Var(value="focus_node")
#     endpoint_uri: Optional[URIRef] = None
#     profile_uri: Optional[URIRef] = None
#
#     construct_triples: Optional[List[SimplifiedTriple]] = []
#     main_where_ggps: Optional[GroupGraphPatternSub] = GroupGraphPatternSub()
#     inner_select: Optional[Union[SubSelect, SubSelectString]] = None
#
#     endpoint_shacl_triples: Optional[List[SimplifiedTriple]] = []
#     endpoint_shacl_gpnt: Optional[List[GraphPatternNotTriples]] = []
#     cql_triples: Optional[List[SimplifiedTriple]] = []
#     cql_gpnt: Optional[List[GraphPatternNotTriples]] = []
#     select_template: Optional[Template] = None
#     sparql: Optional[str] = None
#
#     # Additional fields
#     default_limit: Optional[int] = None
#     default_offset: Optional[int] = None
#     default_order_by: Optional[str] = None
#     default_order_by_desc: Optional[bool] = None
#     runtime_vals_expanded: Optional[Dict] = {}
#     merged_runtime_and_default_vals: Optional[Dict] = {}
#
#     def _expand_runtime_vars(self):
#         for k, v in self.runtime_values.items():
#             if k in ["limit", "offset", "q"]:
#                 self.runtime_vals_expanded[k] = v
#             elif v:
#                 val = IRI(value=v).to_string()
#                 self.runtime_vals_expanded[k] = val
#
#     def _merge_runtime_and_default_vars(self):
#         default_args = {
#             "limit": self.default_limit,
#             "offset": self.default_offset,
#             "order_by": self.default_order_by,
#             "order_by_desc": self.default_order_by_desc,
#         }
#         self.merged_runtime_and_default_vals = default_args | self.runtime_vals_expanded
#
#     def generate_sparql(self):
#         """
#         Generates SPARQL query from Shape profile_graph.
#         """
#         self._expand_runtime_vars()
#         if self.listing_or_object == "listing":
#             self.build_inner_select()
#         self.parse_profile()
#         self._generate_query()
#
#     def _generate_query(self):
#         where = WhereClause(
#             group_graph_pattern=GroupGraphPattern(content=self.main_where_ggps)
#         )
#
#         if self.construct_triples:
#             self.construct_triples.extend(where.collect_triples())
#         else:
#             self.construct_triples = where.collect_triples()
#         self.construct_triples = list(set(self.construct_triples))
#
#         if self.listing_or_object == "listing":
#             gpnt = GraphPatternNotTriples(
#                 content=GroupOrUnionGraphPattern(
#                     group_graph_patterns=[GroupGraphPattern(content=self.inner_select)]
#                 )
#             )
#             self.main_where_ggps.add_pattern(gpnt, prepend=True)
#
#         construct_template = ConstructTemplate(
#             construct_triples=ConstructTriples(triples=self.construct_triples)
#         )
#         solution_modifier = SolutionModifier()
#         query_str = ConstructQuery(
#             construct_template=construct_template,
#             where_clause=where,
#             solution_modifier=solution_modifier,
#         ).to_string()
#         self.sparql = query_str
#
#     def build_inner_select(self):
#         """
#         Either set the focus_node to a URIRef, if a target node is provided, or generate a triple pattern to get list items
#         Generates triples for the endpoint definition with runtime values substituted.
#         """
#         inner_select_ggps = GroupGraphPatternSub()
#
#         self._set_limit_and_offset()
#         self._merge_runtime_and_default_vars()
#
#         # rule_nodes = list(
#         #     self.endpoint_graph.objects(subject=self.endpoint_uri, predicate=SH.rule)
#         # )
#
#         sol_mod, order_by_triple = self._create_focus_node_solution_modifier()
#
#         if self.select_template:
#             # sh:target / sh:select
#             sss = self.create_select_subquery_from_template(sol_mod, order_by_triple)
#             self.inner_select = sss
#
#             # # rule nodes - for CONSTRUCT TRIPLES patterns.
#             # if rule_nodes:
#             #     for rule_node in rule_nodes:
#             #         self._create_construct_triples_from_sh_rules(rule_node)
#
#         else:
#             self.inner_select = SubSelect(
#                 select_clause=SelectClause(variables_or_all=[self.focus_node]),
#                 where_clause=WhereClause(
#                     group_graph_pattern=GroupGraphPattern(content=inner_select_ggps)
#                 ),
#                 solution_modifier=sol_mod,
#             )
#
#             if order_by_triple:
#                 inner_select_ggps.add_triple(order_by_triple)
#
#             # otherwise just use what is provided by the endpoint shapes
#             all_triples = self.endpoint_shacl_triples + self.cql_triples
#             if all_triples:
#                 tb = TriplesBlock(triples=all_triples)
#                 inner_select_ggps.add_pattern(tb)
#
#             all_gpnt = self.endpoint_shacl_gpnt + self.cql_gpnt
#             if all_gpnt:
#                 for gpnt in all_gpnt:
#                     inner_select_ggps.add_pattern(gpnt)
#
#     # def sh_rule_type_conversion(self, items: List):
#     #     """
#     #     Assumes Literals are actually Variables.
#     #     """
#     #     new_items = []
#     #     for item in items:
#     #         if isinstance(item, URIRef):
#     #             item = IRI(value=item)
#     #         elif isinstance(item, Literal):
#     #             item = Var(value=item[1:])
#     #         new_items.append(item)
#     #     return new_items
#     #
#     # def _create_construct_triples_from_sh_rules(self, rule_node):
#     #     """CONSTRUCT {?s ?p ?o} based on sh:rule [ sh:subject ... ]"""
#     #     subject = self.endpoint_graph.value(subject=rule_node, predicate=SH.subject)
#     #     predicate = self.endpoint_graph.value(subject=rule_node, predicate=SH.predicate)
#     #     object = self.endpoint_graph.value(subject=rule_node, predicate=SH.object)
#     #     if subject == SH.this:
#     #         subject = self.focus_node
#     #     subject, predicate, object = self.sh_rule_type_conversion(
#     #         [subject, predicate, object]
#     #     )
#     #
#     #     triple = SimplifiedTriple(subject=subject, predicate=predicate, object=object)
#     #     if self.construct_triples:
#     #         self.construct_triples.append(triple)
#     #     else:
#     #         self.construct_triples = [triple]
#
#     def create_select_subquery_from_template(self, sol_mod, order_by_triple):
#         # expand any prefixes etc. in case the prefixes are not defined in the query this subquery is being inserted
#         # into. NB Shape does provide a mechanism to declare prefixes used in SPARQL target - this has not been
#         # implemented
#         substituted_query = self.select_template.substitute(
#             self.merged_runtime_and_default_vals
#         ).rstrip()
#         if order_by_triple:  # insert it before the end of the string,
#             order_by_triple_text = order_by_triple.to_string()
#             substituted_query = (
#                 substituted_query[:-1] + f"{{{order_by_triple_text}}} }}"
#             )
#         additional_strings = []
#         if self.cql_triples:  # for example from cql
#             additional_strings.append(
#                 TriplesBlock(triples=self.cql_triples).to_string()
#             )
#         if self.cql_gpnt:
#             additional_strings.extend([gpnt.to_string() for gpnt in self.cql_gpnt])
#             substituted_query = self.split_query(substituted_query, additional_strings)
#         sss = SubSelectString(
#             select_string=substituted_query, solution_modifier=sol_mod
#         )
#         return sss
#
#     def split_query(self, original_query, additional_strings: List[str]):
#         # Regex to match the entire structure: 'SELECT ?xxx { ... }'
#         pattern = r"(SELECT\s+[\?\w\s\(\)]+\s*\{)(.*?)(\}\s*)"
#         # Use re.split to split the query based on the pattern
#         parts = re.split(pattern, original_query, flags=re.DOTALL)
#         parts = [part for part in parts if part.strip()]
#         new_parts = [parts[0]] + additional_strings
#         if len(parts) > 1:
#             new_parts.extend(parts[1:])
#         new_query = "".join(part for part in new_parts)
#         return new_query
#
#     def _create_focus_node_solution_modifier(self):
#         """
#         Solution modifiers include LIMIT, OFFSET, ORDER BY clauses.
#         """
#         order_clause = order_by_triple = None  # order clause is optional
#         order_by_path = self.merged_runtime_and_default_vals.get("order_by")
#         if order_by_path:
#             direction = self.merged_runtime_and_default_vals.get("order_by_desc")
#             if direction:
#                 direction = "DESC"
#             else:
#                 direction = "ASC"
#             order_cond = OrderCondition(
#                 var=Var(value="order_by_var"), direction=direction
#             )
#             order_clause = OrderClause(conditions=[order_cond])
#             order_by_triple = SimplifiedTriple(
#                 subject=self.focus_node,
#                 predicate=IRI(value=order_by_path[0]),
#                 object=Var(value="order_by_var"),
#             )
#         limit = int(self.merged_runtime_and_default_vals["limit"])
#         offset = int(self.merged_runtime_and_default_vals["offset"])
#         limit_clause = LimitClause(limit=limit)
#         offset_clause = OffsetClause(offset=offset)
#         limit_offset_clauses = LimitOffsetClauses(
#             limit_clause=limit_clause, offset_clause=offset_clause
#         )
#         sol_mod = SolutionModifier(
#             order_by=order_clause, limit_offset=limit_offset_clauses
#         )
#         return sol_mod, order_by_triple
#
#     def _set_limit_and_offset(self):
#         """
#         Sets the default limit, offset, and ordering for a listing endpoint.
#         """
#         default_limit = next(
#             self.endpoint_graph.objects(
#                 subject=self.endpoint_uri, predicate=SHEXT.limit
#             ),
#             20,
#         )
#         default_offset = next(
#             self.endpoint_graph.objects(
#                 subject=self.endpoint_uri, predicate=SHEXT.offset
#             ),
#             0,
#         )
#         default_order_by = list(
#             self.endpoint_graph.objects(
#                 subject=self.endpoint_uri, predicate=SHEXT.orderBy
#             )
#         )
#
#         self.default_limit = int(default_limit)
#         self.default_offset = int(default_offset)
#
#         # Process each blank node in the default_order_by list
#         for blank_node in default_order_by:
#             # Extract sh:path
#             path = next(self.endpoint_graph.objects(blank_node, SH.path), None)
#             if not path:
#                 continue  # Skip if no sh:path is found
#
#             # Check for sh:desc
#             desc_node = next(self.endpoint_graph.objects(blank_node, SHEXT.desc), None)
#             is_descending = (
#                 True if desc_node and (desc_node == Literal(True)) else False
#             )
#
#             # Add the configuration to the list
#             self.default_order_by = (path,)
#             self.default_order_by_desc = is_descending
#
#     def parse_profile(self):
#         for i, property_node in enumerate(
#             self.profile_graph.objects(subject=self.profile_uri, predicate=SH.property)
#         ):
#             self._parse_property_shapes(property_node, i)
#         self._build_bnode_blocks()
#
    def _build_bnode_blocks(self):
        bnode_depth = list(
            self.profile_graph.objects(
                subject=self.profile_uri, predicate=SHEXT["bnode-depth"]
            )
        )
        if not bnode_depth or bnode_depth == [0]:
            return
        else:
            bnode_depth = int(bnode_depth[0])
        p1 = Var(value="bn_p_1")
        o1 = Var(value="bn_o_1")
        p2 = Var(value="bn_p_2")
        o2 = Var(value="bn_o_2")
        triples_block = TriplesBlock(
            triples=[
                SimplifiedTriple(subject=self.focus_node, predicate=p1, object=o1),
                SimplifiedTriple(subject=o1, predicate=p2, object=o2),
            ]
        )
        o1_pe = PrimaryExpression(content=o1)
        constraint = Constraint(
            content=BuiltInCall.create_with_one_expr("isBLANK", o1_pe)
        )
        filter_block = Filter(constraint=constraint)
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
            old_o_var = Var(value=f"bn_o_{depth}")
            new_p_var = Var(value=f"bn_p_{depth + 1}")
            new_o_var = Var(value=f"bn_o_{depth + 1}")
            triples_block = TriplesBlock(
                triples=[
                    SimplifiedTriple(
                        subject=old_o_var, predicate=new_p_var, object=new_o_var
                    )
                ]
            )
            gpnt = GraphPatternNotTriples(
                content=Filter(
                    constraint=Constraint(
                        content=BuiltInCall.create_with_one_expr(
                            "isBLANK", PrimaryExpression(content=old_o_var)
                        )
                    )
                )
            )
            opt = OptionalGraphPattern(
                group_graph_pattern=GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        triples_block=triples_block,
                        graph_patterns_or_triples_blocks=[gpnt],
                    )
                )
            )
            outer_ggps.graph_patterns_or_triples_blocks.append(opt)
            if depth < max_depth:
                process_bn_level(depth + 1, max_depth, ggps)

        if bnode_depth > 1:
            process_bn_level(depth=2, max_depth=bnode_depth, outer_ggps=ggps)
        gpnt = GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(group_graph_patterns=[container_ggp])
        )
        self.main_where_ggps.add_pattern(gpnt)
#
#     def _parse_property_shapes(self, property_node, i):
#         def process_path_object(path_obj: Union[URIRef, BNode]):
#             if isinstance(path_obj, BNode):
#                 pred_objects_gen = self.profile_graph.predicate_objects(
#                     subject=path_obj
#                 )
#                 bn_pred, bn_obj = next(pred_objects_gen, (None, None))
#                 if bn_obj == SH.union:
#                     pass
#                 elif bn_pred == SH.inversePath:
#                     inverse_preds.append(IRI(value=bn_obj))
#                 elif bn_pred == SH.alternativePath:
#                     predicates.extend(list(Collection(self.profile_graph, bn_obj)))
#                 else:  # sequence paths
#                     predicates.append(tuple(Collection(self.profile_graph, path_obj)))
#             else:  # a plain path specification to restrict the predicate to a specific value
#                 predicates.append(path_obj)
#
#         inverse_preds = []  # list of IRIs
#         predicates = []  # list of IRIs
#         union_items = None
#         path_object = self.profile_graph.value(
#             subject=property_node, predicate=SH.path, default=None
#         )
#         if isinstance(path_object, BNode):
#             predicate_objects_gen = self.profile_graph.predicate_objects(
#                 subject=path_object
#             )
#             bnode_pred, bnode_obj = next(predicate_objects_gen, (None, None))
#             if bnode_obj == SH.union:  # TODO or sh:or ??
#                 union_list_bnode = list(Collection(self.profile_graph, path_object))[1]
#                 union_items = list(Collection(self.profile_graph, union_list_bnode))
#
#         ggp_list = []
#         if union_items:
#             for item in union_items:
#                 process_path_object(item)
#         else:
#             process_path_object(path_object)
#
#         if inverse_preds:
#             ggps_under_under_union = GroupGraphPatternSub()
#             ggps = ggps_under_under_union
#             ggp = GroupGraphPattern(content=ggps_under_under_union)
#             ggp_list.append(ggp)
#             self._add_inverse_preds(ggps, inverse_preds, i)
#         if predicates:
#             self._add_predicate_constraints(predicates, property_node, ggp_list)
#         self._add_object_constraints(ggp_list, property_node)
#         union = GroupOrUnionGraphPattern(group_graph_patterns=ggp_list)
#         gpnt = GraphPatternNotTriples(content=union)
#
#         min = int(
#             self.profile_graph.value(
#                 subject=property_node, predicate=SH.minCount, default=1
#             )
#         )
#         if min == 0:  # Add Optional GroupGraphPatternSub "wrapper" as the main GGPS
#             ggps_under_optional = GroupGraphPatternSub(
#                 graph_patterns_or_triples_blocks=[gpnt]
#             )
#             ggp = GroupGraphPattern(content=ggps_under_optional)
#             optional = OptionalGraphPattern(group_graph_pattern=ggp)
#             gpnt = GraphPatternNotTriples(content=optional)
#         self.main_where_ggps.add_pattern(gpnt)
#
#     def _add_inverse_preds(
#         self, ggps: GroupGraphPatternSub, inverse_preds: List[IRI], i
#     ):
#         if inverse_preds:
#             ggps.add_triple(
#                 SimplifiedTriple(
#                     subject=Var(value=f"inv_path_{i}"),
#                     predicate=Var(value=f"inv_pred_{i}"),
#                     object=self.focus_node,
#                 )
#             )
#             dbv_list = [DataBlockValue(value=p) for p in inverse_preds]
#             ildov = InlineDataOneVar(
#                 variable=Var(value=f"inv_pred_{i}"), datablockvalues=dbv_list
#             )
#             data_block = DataBlock(block=ildov)
#             inline_data = InlineData(data_block=data_block)
#             gpnt = GraphPatternNotTriples(content=inline_data)
#             ggps.add_pattern(gpnt)
#
#     def _add_predicate_constraints(self, predicates, property_node, ggp_list):
#         # check for any sequence paths - process separately
#         sps = [p for p in predicates if isinstance(p, tuple)]  # convert to IRIs here
#         predicates = [
#             IRI(value=p) for p in predicates if not isinstance(p, tuple)
#         ]  # convert to IRIs below
#
#         try:
#             for i, (pred1, pred2) in enumerate(sps):
#                 t1 = SimplifiedTriple(
#                     subject=self.focus_node,
#                     predicate=IRI(value=pred1),
#                     object=Var(value=f"seq_obj_{i + 1}"),
#                 )
#                 t2 = SimplifiedTriple(
#                     subject=Var(value=f"seq_obj_{i + 1}"),
#                     predicate=IRI(value=pred2),
#                     object=Var(value=f"seq_obj_terminal{i + 1}"),
#                 )
#                 tb = TriplesBlock(triples=[t1, t2])
#                 ggps = GroupGraphPatternSub(triples_block=tb)
#                 ggp = GroupGraphPattern(content=ggps)
#                 ggp_list.append(ggp)
#         except Exception as e:
#             print(e)
#
#         # process direct path predicates
#         max = self.profile_graph.value(subject=property_node, predicate=SH.maxCount)
#         simplified_triple = SimplifiedTriple(
#             subject=self.focus_node,
#             predicate=Var(value="preds"),
#             object=Var(value="objs"),
#         )
#         tb = TriplesBlock(triples=[simplified_triple])
#         if predicates:
#             if max == Literal(0):  # excluded predicates.
#                 values = [
#                     PrimaryExpression(content=IRIOrFunction(iri=p)) for p in predicates
#                 ]
#                 focus_pe = PrimaryExpression(content=Var(value="preds"))
#                 values_constraint = Filter.filter_relational(
#                     focus=focus_pe, comparators=values, operator="NOT IN"
#                 )
#                 gpnt = GraphPatternNotTriples(content=values_constraint)
#                 if ggp_list:
#                     for ggp in ggp_list:
#                         ggp.content.add_pattern(gpnt)
#                 else:
#                     ggps = GroupGraphPatternSub(
#                         graph_patterns_or_triples_blocks=[gpnt, tb]
#                     )
#                     ggp = GroupGraphPattern(content=ggps)
#                     ggp_list.append(ggp)
#             elif (
#                 IRI(value=SHEXT.allPredicateValues) not in predicates
#             ):  # add VALUES clause
#                 dbv_list = [DataBlockValue(value=p) for p in predicates]
#                 inline_data_one_var = InlineDataOneVar(
#                     variable=Var(value="preds"), datablockvalues=dbv_list
#                 )
#                 data_block = DataBlock(block=inline_data_one_var)
#                 inline_data = InlineData(data_block=data_block)
#                 gpnt = GraphPatternNotTriples(content=inline_data)
#                 ggps = GroupGraphPatternSub(graph_patterns_or_triples_blocks=[gpnt, tb])
#                 ggp = GroupGraphPattern(content=ggps)
#                 ggp_list.append(ggp)
#             elif predicates == [IRI(value=SHEXT.allPredicateValues)]:
#                 ggps = GroupGraphPatternSub(triples_block=tb)
#                 ggp = GroupGraphPattern(content=ggps)
#                 ggp_list.append(ggp)
#
#     def _add_object_constraints(self, ggp_list, property_node):
#         value = self.profile_graph.value(
#             subject=property_node, predicate=SH.hasValue, default=None
#         )
#         values_bn = self.profile_graph.value(
#             subject=property_node, predicate=SH["in"], default=None
#         )
#         if value:  # a specific value
#             objects = [value]
#         elif values_bn:  # a set of values
#             c = Collection(self.profile_graph, values_bn)
#             objects = list(c)
#         if value or values_bn:
#             ggps = GroupGraphPatternSub()
#             ggp = GroupGraphPattern(content=ggps)
#             ggp_list.append(ggp)
#             objs = []
#             for obj in objects:
#                 if isinstance(obj, Literal):
#                     objs.append(RDFLiteral(value=obj))
#                 elif isinstance(obj, URIRef):
#                     objs.append(IRI(value=obj))
#             dbv_list = [DataBlockValue(value=p) for p in objs]
#             inline_data_one_var = InlineDataOneVar(
#                 variable=Var(value="objs"), datablockvalues=dbv_list
#             )
#             data_block = DataBlock(block=inline_data_one_var)
#             inline_data = InlineData(data_block=data_block)
#             gpnt = GraphPatternNotTriples(content=inline_data)
#             ggps.add_pattern(gpnt)


class PrezQueryConstructorV2(ConstructQuery):
    """
    Creates a CONSTRUCT query to describe a listing of objects or an individual object.
    Query format:

    CONSTRUCT {
        <construct_triples + additional_construct_triples>
    }
    WHERE {
        <profile_triples>
        <profile_gpnt>
        # for listing queries only:
        { SELECT ?focus_node <innser_select_vars>
            WHERE {
                <inner_select_triples>
                <inner_select_gpnt>
            }
            ORDER BY <order_by_direction>(<order_by>)
            LIMIT <limit>
            OFFSET <offset>
        }
    }
    gpnt = GraphPatternNotTriples - refer to the SPARQL grammar for details.
    """

    def __init__(
        self,
        additional_construct_triples: Optional[List[SimplifiedTriple]] = [],
        profile_triples: Optional[List[SimplifiedTriple]] = [],
        profile_gpnt: Optional[List[GraphPatternNotTriples]] = [],
        inner_select_vars: Optional[List[Union[Var, Tuple[Expression, Var]]]] = [],
        inner_select_triples: Optional[List[SimplifiedTriple]] = [],
        inner_select_gpnt: Optional[List[GraphPatternNotTriples]] = [],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[Var] = None,
        order_by_direction: Optional[str] = None,
    ):
        # where clause triples and GraphPatternNotTriples - set up first as in the case of a listing query, the inner
        # select is appended to this list as a GraphPatternNotTriples
        gpotb = [TriplesBlock(triples=profile_triples), *profile_gpnt]

        # inner_select_vars typically set for search queries or custom select queries; otherwise we only want the focus
        # node from the inner select query
        if not inner_select_vars:
            inner_select_vars = [(Var(value="focus_node"))]

        # order condition
        oc = None
        if order_by:
            oc = OrderClause(
                conditions=[
                    OrderCondition(
                        var=order_by,  # ORDER BY
                        direction=order_by_direction,  # DESC/ASC
                    )
                ]
            )

        # for listing queries only, add an inner select to the where clause
        if inner_select_triples or inner_select_gpnt:
            gpnt_inner_subselect = GraphPatternNotTriples(
                content=GroupOrUnionGraphPattern(
                    group_graph_patterns=[
                        GroupGraphPattern(
                            content=SubSelect(
                                select_clause=SelectClause(
                                    distinct=True,
                                    variables_or_all=inner_select_vars
                                ),
                                where_clause=WhereClause(
                                    group_graph_pattern=GroupGraphPattern(
                                        content=GroupGraphPatternSub(
                                            graph_patterns_or_triples_blocks=[
                                                TriplesBlock(
                                                    triples=inner_select_triples
                                                ),
                                                *inner_select_gpnt,
                                            ]
                                        )
                                    )
                                ),
                                solution_modifier=SolutionModifier(
                                    limit_offset=LimitOffsetClauses(
                                        limit_clause=LimitClause(
                                            limit=limit
                                        ),  # LIMIT m
                                        offset_clause=OffsetClause(
                                            offset=offset
                                        ),  # OFFSET n
                                    ),
                                    order_by=oc
                                ),
                            )
                        )
                    ]
                )
            )
            gpotb.append(gpnt_inner_subselect)
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(graph_patterns_or_triples_blocks=gpotb)
            )
        )

        # construct triples is usually only from the profile, but in the case of search queries for example, additional
        # triples are added
        construct_triples = TriplesBlock(triples=profile_triples).collect_triples()
        if additional_construct_triples:
            construct_triples.extend(additional_construct_triples)
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples(triples=construct_triples)
        )
        super().__init__(
            construct_template=construct_template,
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )

    @property
    def inner_select(self):
        return self.where_clause.group_graph_pattern.content.graph_patterns_or_triples_blocks[-1].content.group_graph_patterns[0].content


# def get_profile_grammar(profile_uri: URIRef):
#     """
#     Returns the grammar for a given profile.
#     """
#     profile = NodeShape(uri=profile_uri, graph=profiles_graph_cache, kind="profile")
#     return profile.triples_list, profile.gpnt_list
#
#
# def get_endpoint_grammar(endpoint_uri: URIRef):
#     """
#     Returns the grammar for a given endpoint.
#     """
#     endpoint_shape = NodeShape(
#         uri=endpoint_uri, graph=endpoints_graph_cache, kind="endpoint"
#     )
#     return endpoint_shape.triples_list, endpoint_shape.gpnt_list
#
#
# def get_cql_grammar():
#     pass
#
#
# def get_search_grammar():
#     pass
#
#
# def get_all_grammar():
#     pass


def merge_listing_query_grammar_inputs(
    cql_parser: Optional[CQLParser] = None,
    endpoint_nodeshape: Optional[NodeShape] = None,
    search_query: Optional[SearchQueryRegex] = None,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    order_by: Optional[str] = None,
    order_by_direction: Optional[bool] = None,
) -> dict:
    """
    Merges the inputs for a query grammar.
    """
    kwargs = {
        "additional_construct_triples": None,
        "inner_select_vars": [],
        "inner_select_triples": [],
        "inner_select_gpnt": [],
        "limit": None,
        "offset": None,
        "order_by": order_by,
        "order_by_direction": order_by_direction,
    }
    if search_query:
        kwargs["additional_construct_triples"] = search_query.construct_triples
        kwargs["inner_select_vars"] = search_query.inner_select_vars
        kwargs["limit"] = search_query.limit
        kwargs["offset"] = search_query.offset
        kwargs["order_by"] = search_query.order_by
        kwargs["order_by_direction"] = search_query.order_by_direction
        kwargs["inner_select_gpnt"] = [search_query.inner_select_gpnt]
    else:
        limit = int(per_page)
        offset = limit * (int(page) - 1)
        kwargs["limit"] = limit
        kwargs["offset"] = offset
        if order_by:
            kwargs["order_by"] = Var(value=order_by)
            if order_by_direction:
                kwargs["order_by_direction"] = order_by_direction
            else:
                kwargs["order_by_direction"] = "ASC"

    if cql_parser:
        pass

    if endpoint_nodeshape:
        kwargs["inner_select_triples"].extend(endpoint_nodeshape.triples_list)
        kwargs["inner_select_gpnt"].extend(endpoint_nodeshape.gpnt_list)

    return kwargs
