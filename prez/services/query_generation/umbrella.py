from typing import List, Optional, Tuple, Union

from rdflib import URIRef
from sparql_grammar_pydantic import (
    Constraint,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    GraphPatternNotTriples,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitClause,
    LimitOffsetClauses,
    OffsetClause,
    OrderClause,
    OrderCondition,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
    IRI,
    BuiltInCall,
    PrimaryExpression
)

from prez.models.query_params import ListingQueryParams
from prez.services.query_generation.bbox_filter import generate_bbox_filter
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.datetime_filter import generate_datetime_filter
from prez.services.query_generation.search_default import SearchQueryRegex
from prez.services.query_generation.search_fuseki_fts import SearchQueryFusekiFTS
from prez.services.query_generation.shacl import NodeShape


class PrezQueryConstructor(ConstructQuery):
    """
    Creates a CONSTRUCT query to describe a listing of objects or an individual object.
    Query format:

    CONSTRUCT {
        <construct_triples + construct_tss_list>
    }
    WHERE {
        # for listing queries only:
        { SELECT ?focus_node <innser_select_vars>
            WHERE {
                <inner_select_tssp_list>
                <inner_select_gpnt>
                ?focus_node <order_by_predicate> <order_by_value>  # where order_by is specified
            }
            ORDER BY <order_by_direction>(<order_by_value>)
            LIMIT <limit>
            OFFSET <offset>
        }
        <profile_triples>
        <profile_gpnt>
    }
    gpnt = GraphPatternNotTriples - refer to the SPARQL grammar for details.
    """

    def __init__(
        self,
        construct_tss_list: Optional[List[TriplesSameSubject]] = None,
        profile_triples: Optional[List[TriplesSameSubjectPath]] = [],
        profile_gpnt: Optional[List[GraphPatternNotTriples]] = [],
        inner_select_vars: Optional[List[Union[Var, Tuple[Expression, Var]]]] = [],
        inner_select_tssp_list: Optional[List[TriplesSameSubjectPath]] = [],
        inner_select_gpnt: Optional[List[GraphPatternNotTriples]] = [],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by_predicate: Optional[IRI] = None,
        order_by_value: Optional[Var] = None,
        order_by_direction: Optional[str] = None,
    ):
        # where clause triples and GraphPatternNotTriples - set up first as in the case of a listing query, the inner
        # select is appended to this list as a GraphPatternNotTriples
        gpotb = []
        if profile_triples:
            gpotb.append(TriplesBlock.from_tssp_list(profile_triples))
        if profile_gpnt:
            gpotb.extend(profile_gpnt)

        # inner_select_vars typically set for search queries or custom select queries; otherwise we only want the focus
        # node from the inner select query
        if not inner_select_vars:
            inner_select_vars = [(Var(value="focus_node"))]

        # order condition
        oc = None
        if order_by_predicate and not order_by_value:
            # this scenario should only occur if the PrezQueryConstructor is called directly e.g. in tests. When using
            # the merge inputs function, either both or only order_by_value will be set AND where only
            # order_by_predicate is set (e.g. search queries), the order_by_value (=?weight) is bound in the GPNT.
            order_by_value = Var(value="order_by_val")

        if order_by_value:
            if order_by_value.value == "weight":
                constraint_or_var = order_by_value  # NO string function to get correct numerical ordering
            elif order_by_value.value in ("label", "order_by_val"):  # STR function in order to "ignore" langtags
                constraint_or_var = Constraint(
                            content=BuiltInCall.create_with_one_expr(
                                function_name="STR",
                                expression=PrimaryExpression(
                                    content=order_by_value)
                            )
                        )
            else:
                raise ValueError("order by value must be \"label\", \"order_by_val\", or \"weight\" to work with "
                                 "automated query generation")
            oc = OrderClause(
                conditions=[
                    OrderCondition(
                        constraint_or_var=constraint_or_var,
                        direction=order_by_direction,  # DESC/ASC
                    )
                ]
            )
        if order_by_predicate:
            tssp = TriplesSameSubjectPath.from_spo(
                        subject=Var(value="focus_node"),
                        predicate=order_by_predicate,
                        object=order_by_value
                    )
            if inner_select_tssp_list:
                inner_select_tssp_list.append(tssp)
            else:
                inner_select_tssp_list = [tssp]

        # for listing queries only, add an inner select to the where clause
        ss_gpotb = []
        if inner_select_tssp_list:
            inner_select_tssp_list = sorted(
                inner_select_tssp_list, key=lambda x: str(x), reverse=True
            )  # grouping for performance
            ss_gpotb.append(TriplesBlock.from_tssp_list(inner_select_tssp_list))
        if inner_select_gpnt:
            ss_gpotb.extend(inner_select_gpnt)

        if inner_select_tssp_list or inner_select_gpnt:
            gpnt_inner_subselect = GraphPatternNotTriples(
                content=GroupOrUnionGraphPattern(
                    group_graph_patterns=[
                        GroupGraphPattern(
                            content=SubSelect(
                                select_clause=SelectClause(
                                    distinct=True, variables_or_all=inner_select_vars
                                ),
                                where_clause=WhereClause(
                                    group_graph_pattern=GroupGraphPattern(
                                        content=GroupGraphPatternSub(
                                            graph_patterns_or_triples_blocks=ss_gpotb
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
                                    order_by=oc,
                                ),
                            )
                        )
                    ]
                )
            )
            # insert at start so that subselect is first for performant SPARQL query
            gpotb.insert(0, gpnt_inner_subselect)
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(graph_patterns_or_triples_blocks=gpotb)
            )
        )

        # construct triples is usually only from the profile, but in the case of search queries for example, additional
        # triples are added
        construct_triples = None
        if construct_tss_list:
            construct_triples = ConstructTriples.from_tss_list(construct_tss_list)

        construct_template = ConstructTemplate(construct_triples=construct_triples)
        super().__init__(
            construct_template=construct_template,
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )

    @property
    def inner_select(self):
        return (
            self.where_clause.group_graph_pattern.content.graph_patterns_or_triples_blocks[
                0
            ]
            .content.group_graph_patterns[0]
            .content
        )


def merge_listing_query_grammar_inputs(
    cql_parser: Optional[CQLParser] = None,
    endpoint_nodeshape: Optional[NodeShape] = None,
    search_query: Optional[SearchQueryRegex | SearchQueryFusekiFTS] = None,
    concept_hierarchy_query: Optional[ConceptHierarchyQuery] = None,
    query_params: Optional[ListingQueryParams] = None,
) -> dict:
    page = query_params.page
    limit = query_params.limit
    startindex = query_params.startindex
    order_by = query_params.order_by
    order_by_direction = query_params.order_by_direction
    bbox = query_params.bbox
    datetime = query_params.datetime
    filter_crs = query_params.filter_crs
    """
    Merges the inputs for a query grammar.
    """
    kwargs = {
        "construct_tss_list": [],
        "inner_select_vars": [Var(value="focus_node")],
        "inner_select_tssp_list": [],
        "inner_select_gpnt": [],
        "limit": None,
        "offset": None,
        "order_by_predicate": order_by,
        "order_by_value": None,
        "order_by_direction": order_by_direction,
    }

    limit = int(limit)
    if startindex:
        offset = startindex
    else:
        offset = limit * (int(page) - 1)
    kwargs["limit"] = limit
    kwargs["offset"] = offset
    if concept_hierarchy_query:
        kwargs["construct_tss_list"] = concept_hierarchy_query.tss_list
        kwargs["inner_select_vars"] = concept_hierarchy_query.inner_select_vars
        if order_by:
            kwargs["order_by_predicate"] = IRI(value=order_by)  # from QSA
        else:
            kwargs["order_by_value"] = concept_hierarchy_query.order_by_val  # from query itself, hardcoded to "?label"
        if order_by_direction:
            kwargs["order_by_direction"] = order_by_direction
        else:
            kwargs["order_by_direction"] = "ASC"
        kwargs["inner_select_gpnt"] = [concept_hierarchy_query.inner_select_gpnt]

    # TODO can remove limit/offset/order by from search query - apply from QSA or defaults.
    if search_query:
        kwargs["construct_tss_list"].extend(search_query.tss_list)
        kwargs["inner_select_vars"].extend(search_query.inner_select_vars)
        kwargs["limit"] = search_query.limit
        kwargs["offset"] = search_query.offset
        kwargs["order_by_value"] = search_query.order_by_val
        kwargs["order_by_direction"] = search_query.order_by_direction
        kwargs["inner_select_gpnt"].extend([search_query.inner_select_gpnt])

    if cql_parser:
        kwargs["inner_select_vars"].extend(cql_parser.inner_select_vars)
        kwargs["construct_tss_list"].extend(cql_parser.tss_list)
        kwargs["inner_select_tssp_list"].extend(cql_parser.tssp_list)
        kwargs["inner_select_gpnt"].extend(cql_parser.inner_select_gpnt_list)

    if endpoint_nodeshape:
        # endpoint nodeshape will constrain the focus nodes selected - undesirable for plain search/CQL. However, if
        # search/CQL is used on a generic listing endpoint, then we do want both the endpoint nodeshape (which
        # constrains the focus nodes) + the search/CQL query.
        if endpoint_nodeshape.uri not in [URIRef('http://example.org/ns#Search'), URIRef('http://example.org/ns#CQL')]:
            kwargs["inner_select_tssp_list"].extend(endpoint_nodeshape.tssp_list)
            kwargs["inner_select_gpnt"].extend(endpoint_nodeshape.gpnt_list)

    if bbox:
        gpnt_list, tssp_list = generate_bbox_filter(bbox, filter_crs)
        kwargs["inner_select_gpnt"].extend(gpnt_list)
        kwargs["inner_select_tssp_list"].extend(tssp_list)

    if datetime:
        gpnt_list, tssp_list = generate_datetime_filter(*datetime)
        kwargs["inner_select_gpnt"].extend(gpnt_list)
        kwargs["inner_select_tssp_list"].extend(tssp_list)

    if order_by:  # order by comes from query param - this will override the default order by in search and concept
        # hierarchy queries
        kwargs["order_by_predicate"] = IRI(value=order_by)
        kwargs["order_by_value"] = Var(value="order_by_val")
        kwargs["order_by_direction"] = order_by_direction or "ASC"

    return kwargs
