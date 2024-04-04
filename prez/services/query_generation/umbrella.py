from typing import Union, Optional, List

from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.search import SearchQueryRegex
from prez.services.query_generation.shacl import NodeShape
from temp.grammar import *


class PrezQueryConstructor(ConstructQuery):
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
                                    distinct=True, variables_or_all=inner_select_vars
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
                                    order_by=oc,
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
        # triples from any profiles gpnt
        for gpnt in profile_gpnt:
            construct_triples.extend(gpnt.collect_triples())
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
        return (
            self.where_clause.group_graph_pattern.content.graph_patterns_or_triples_blocks[
                -1
            ]
            .content.group_graph_patterns[0]
            .content
        )


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
