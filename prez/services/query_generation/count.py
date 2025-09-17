from sparql_grammar_pydantic import (
    IRI,
    AdditiveExpression,
    Aggregate,
    Anon,
    Bind,
    BlankNode,
    BuiltInCall,
    ConditionalAndExpression,
    ConditionalOrExpression,
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
    MultiplicativeExpression,
    NumericExpression,
    NumericLiteral,
    PrimaryExpression,
    RDFLiteral,
    RelationalExpression,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesSameSubject,
    UnaryExpression,
    ValueLogical,
    Var,
    WhereClause,
)

from prez.config import settings


class CountQuery(ConstructQuery):
    """
    Counts focus nodes that can be retrieved for listing queries.
    Default limit is 100 and can be configured in the settings.

    Query is of the form:
    CONSTRUCT {
      []  <https://prez.dev/count> ?count_str
    }
    WHERE {
      {
        SELECT (COUNT(?focus_node) AS ?count)
        WHERE {
          SELECT DISTINCT ?focus_node
          WHERE {
            <<< original where clause >>>
          } LIMIT 101
        }
      }
      BIND(IF(?count = 101, ">100", STR(?count)) AS ?count_str)
    }
    """

    def __init__(self, original_subselect: SubSelect):
        """
        Handles pagination limits by comparing the requested range (offset + limit) against a configured maximum.
        Preserves the original range if it already exceeds the maximum, otherwise defaults to the system-defined limit.
        This limit then has one added so that the UI knows if there is more data available.
        """
        current_offset = (
            original_subselect.solution_modifier.limit_offset.offset_clause.offset
        )
        current_limit = (
            original_subselect.solution_modifier.limit_offset.limit_clause.limit
        )
        if (current_offset + current_limit) > settings.listing_count_limit:
            limit = current_offset + current_limit
        else:
            limit = settings.listing_count_limit
        limit_plus_one = limit + 1
        inner_ss = SubSelect(
            select_clause=SelectClause(
                variables_or_all=[Var(value="focus_node")],
                distinct=True,
            ),
            where_clause=original_subselect.where_clause,
            solution_modifier=SolutionModifier(
                limit_offset=LimitOffsetClauses(
                    limit_clause=LimitClause(limit=limit_plus_one)
                ),
            ),
            values_clause=original_subselect.values_clause,
        )
        count_expression = Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall(
                    other_expressions=Aggregate(
                        function_name="COUNT",
                        expression=Expression.from_primary_expression(
                            PrimaryExpression(content=Var(value="focus_node"))
                        ),
                    )
                )
            )
        )
        outer_ss = SubSelect(
            select_clause=SelectClause(
                variables_or_all=[(count_expression, Var(value="count"))],
            ),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(content=inner_ss)
            ),
        )
        outer_ss_ggp = GroupGraphPattern(content=outer_ss)
        count_equals_limit_expr = Expression(
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
                                                    primary_expression=PrimaryExpression(
                                                        content=Var(value="count")
                                                    )
                                                )
                                            )
                                        )
                                    ),
                                    operator="=",
                                    right=NumericExpression(
                                        additive_expression=AdditiveExpression(
                                            base_expression=MultiplicativeExpression(
                                                base_expression=UnaryExpression(
                                                    primary_expression=PrimaryExpression(
                                                        content=NumericLiteral(
                                                            value=limit_plus_one
                                                        )
                                                    )
                                                )
                                            )
                                        )
                                    ),
                                )
                            )
                        ]
                    )
                ]
            )
        )
        gt_limit_exp = Expression.from_primary_expression(
            PrimaryExpression(content=RDFLiteral(value=f">{limit}"))
        )
        str_count_exp = Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall.create_with_one_expr(
                    function_name="STR",
                    expression=PrimaryExpression(content=Var(value="count")),
                )
            )
        )
        bind = Bind(
            expression=Expression.from_primary_expression(
                PrimaryExpression(
                    content=BuiltInCall(
                        function_name="IF",
                        arguments=[
                            count_equals_limit_expr,
                            gt_limit_exp,
                            str_count_exp,
                        ],
                    )
                )
            ),
            var=Var(value="count_str"),
        )
        wc = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[
                        GraphPatternNotTriples(
                            content=GroupOrUnionGraphPattern(
                                group_graph_patterns=[outer_ss_ggp]
                            )
                        ),
                        GraphPatternNotTriples(content=bind),
                    ]
                )
            )
        )
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(
                [
                    TriplesSameSubject.from_spo(
                        subject=BlankNode(value=Anon()),
                        predicate=IRI(value="https://prez.dev/count"),
                        object=Var(value="count_str"),
                    )
                ]
            )
        )
        # Initialize the base ConstructQuery
        super().__init__(
            construct_template=construct_template,
            where_clause=wc,
            solution_modifier=SolutionModifier(),
        )


def startup_count_objects():
    """
    Retrieves hardcoded counts for collections in the repository (Feature Collections, Catalogs etc.)
    """
    return """PREFIX prez: <https://prez.dev/>
                CONSTRUCT { ?collection prez:count ?count }
                WHERE { ?collection prez:count ?count }"""
