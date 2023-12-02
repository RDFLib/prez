from sparql_grammar_pydantic import (
    ConstructQuery,
    IRI,
    Var,
    Expression,
    PrimaryExpression,
    BuiltInCall,
    ConstructTemplate,
    ConstructTriples,
    TriplesSameSubject,
    WhereClause,
    GroupGraphPattern,
    SolutionModifier,
    SubSelect,
    BlankNode,
    Anon,
    Aggregate,
    SelectClause,
)


class CountQuery(ConstructQuery):
    """Query is of the form:
    CONSTRUCT {
    _:N9008750f9acb47c08dfc2c3ae72ede37 <https://prez.dev/count> ?count .
        }
        WHERE {
        SELECT (COUNT(DISTINCT ?focus_node) AS ?count)
            WHERE {
                <<<from original SubSelect>>>
            }
    }
    """

    def __init__(self, original_subselect: SubSelect):
        # Construct Template
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(
                [
                    TriplesSameSubject.from_spo(
                        subject=BlankNode(value=Anon()),
                        predicate=IRI(value="https://prez.dev/count"),
                        object=Var(value="count"),
                    )
                ]
            )
        )

        # Rebuild the SELECT clause in the new SubSelect to retrieve the count of the focus node
        count_expression = Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall(
                    other_expressions=Aggregate(
                        function_name="COUNT",
                        distinct=True,
                        expression=Expression.from_primary_expression(
                            PrimaryExpression(content=Var(value="focus_node"))
                        ),
                    )
                )
            )
        )

        # Where Clause using the new SubSelect
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=SubSelect(
                    select_clause=SelectClause(
                        variables_or_all=[(count_expression, Var(value="count"))],
                    ),
                    where_clause=original_subselect.where_clause,
                    values_clause=original_subselect.values_clause,
                    solution_modifier=SolutionModifier(),
                )
            )
        )
        # Initialize the base ConstructQuery
        super().__init__(
            construct_template=construct_template,
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )


def startup_count_objects():
    """
    Retrieves hardcoded counts for collections in the repository (Feature Collections, Catalogs etc.)
    """
    return f"""PREFIX prez: <https://prez.dev/>
                CONSTRUCT {{ ?collection prez:count ?count }}
                WHERE {{ ?collection prez:count ?count }}"""
