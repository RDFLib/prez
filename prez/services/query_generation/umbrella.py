from typing import Union, Optional, List, Tuple

from sparql_grammar_pydantic import (
    ConstructQuery,
    Var,
    GraphPatternNotTriples,
    Expression,
    ConstructTemplate,
    ConstructTriples,
    TriplesSameSubject,
    WhereClause,
    GroupGraphPattern,
    GroupGraphPatternSub,
    TriplesBlock,
    TriplesSameSubjectPath,
    SolutionModifier,
    SelectClause,
    LimitOffsetClauses,
    LimitClause,
    OffsetClause,
    GroupOrUnionGraphPattern,
    OrderClause,
    OrderCondition,
    SubSelect,
)

from prez.models.query_params import QueryParams
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
            }
            ORDER BY <order_by_direction>(<order_by>)
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
        order_by: Optional[Var] = None,
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
    query_params: Optional[QueryParams] = None,
) -> dict:
    page = query_params.page
    limit = query_params.limit
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
        "order_by": order_by,
        "order_by_direction": order_by_direction,
    }

    limit = int(limit)
    offset = limit * (int(page) - 1)
    kwargs["limit"] = limit
    kwargs["offset"] = offset
    if concept_hierarchy_query:
        kwargs["construct_tss_list"] = concept_hierarchy_query.tss_list
        kwargs["inner_select_vars"] = concept_hierarchy_query.inner_select_vars
        if order_by:
            kwargs["order_by"] = Var(value=order_by)
        else:
            kwargs["order_by"] = concept_hierarchy_query.order_by
        if order_by_direction:
            kwargs["order_by_direction"] = order_by_direction
        else:
            kwargs["order_by_direction"] = "ASC"
            # kwargs["order_by_direction"] = concept_hierarchy_query.order_by_direction  # not implemented
        kwargs["inner_select_gpnt"] = [concept_hierarchy_query.inner_select_gpnt]

    # TODO can remove limit/offset/order by from search query - apply from QSA or defaults.
    if search_query:
        kwargs["construct_tss_list"].extend(search_query.tss_list)
        kwargs["inner_select_vars"].extend(search_query.inner_select_vars)
        kwargs["limit"] = search_query.limit
        kwargs["offset"] = search_query.offset
        kwargs["order_by"] = search_query.order_by
        kwargs["order_by_direction"] = search_query.order_by_direction
        kwargs["inner_select_gpnt"].extend([search_query.inner_select_gpnt])
    else:
        if order_by:
            kwargs["order_by"] = Var(value=order_by)
            if order_by_direction:
                kwargs["order_by_direction"] = order_by_direction
            else:
                kwargs["order_by_direction"] = "ASC"

    if cql_parser:
        kwargs["inner_select_vars"].extend(cql_parser.inner_select_vars)
        kwargs["construct_tss_list"].extend(cql_parser.tss_list)
        kwargs["inner_select_tssp_list"].extend(cql_parser.tssp_list)
        kwargs["inner_select_gpnt"].extend(cql_parser.inner_select_gpnt_list)

    if endpoint_nodeshape:
        kwargs["inner_select_tssp_list"].extend(endpoint_nodeshape.tssp_list)
        kwargs["inner_select_gpnt"].extend(endpoint_nodeshape.gpnt_list)

    if bbox:
        gpnt, tssp_list = generate_bbox_filter(bbox, filter_crs)
        kwargs["inner_select_gpnt"].append(gpnt)
        kwargs["inner_select_tssp_list"].extend(tssp_list)

    if datetime:
        gpnt_list, tssp_list = generate_datetime_filter(*datetime)
        kwargs["inner_select_gpnt"].extend(gpnt_list)
        kwargs["inner_select_tssp_list"].extend(tssp_list)

    return kwargs
