from pydantic import BaseModel
from rdflib import BNode

from prez.reference_data.prez_ns import PREZ
from temp.grammar import *


class CountQuery(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    subselect: SubSelect

    def render(self):
        cq = self.create_construct_query()
        return cq

    def create_construct_query(self):
        """Calls lower level functions and builds the overall query.
        Query is of the form:
        CONSTRUCT {
        _:N9008750f9acb47c08dfc2c3ae72ede37 <https://prez.dev/count> ?count .
            }
            WHERE {
            SELECT (COUNT(DISTINCT ?focus_node) AS ?count)
            WHERE {
                <<<from SHACL node selection>>>
            }
        }
        """
        self.remove_limit_and_offset()
        self.rebuild_select_clause()
        cq = ConstructQuery(
            construct_template=self.create_construct_template(),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(content=self.subselect)
            ),
            solution_modifier=SolutionModifier(),
        )
        return cq

    def remove_limit_and_offset(self):
        """Removes the LIMIT and OFFSET clauses from the original subselect query,
        such that the count of all member objects can be obtained."""
        self.subselect.solution_modifier = None

    def rebuild_select_clause(self):
        """
        Rebuilds the SELECT clause to retrieve the count of the focus node.
        SELECT (COUNT(DISTINCT ?focus_node) AS ?count)
        """
        sc = SelectClause(
            variables_or_all=[
                (
                    Expression.from_primary_expr(
                        PrimaryExpression(
                            content=BuiltInCall(
                                other_expressions=Aggregate(
                                    function_name="COUNT",
                                    distinct=True,
                                    expression=Expression.from_primary_expr(
                                        PrimaryExpression(
                                            content=Var(value="focus_node")
                                        )
                                    ),
                                )
                            )
                        )
                    ),
                    Var(value="count"),
                )
            ]
        )
        self.subselect.select_clause = sc

    def create_construct_template(self):
        """
        Generates a triple for the CONSTRUCT query of the form:
        {
        _:N38355498469c47c5bb1dfa5b34a73df0 <https://prez.dev/count> ?count .
        }
        """
        bn = BlankNode(value=BlankNodeLabel(part_1=BNode()))
        search_result_triples = [
            SimplifiedTriple(
                subject=bn,
                predicate=IRI(value=PREZ["count"]),
                object=Var(value="count"),
            )
        ]
        ct = ConstructTemplate(
            construct_triples=ConstructTriples(triples=search_result_triples)
        )
        return ct


class CountQueryV2(ConstructQuery):
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
            construct_triples=ConstructTriples(
                triples=[
                    SimplifiedTriple(
                        subject=BlankNode(value=Anon()),
                        predicate=IRI(value="https://prez.dev/count"),
                        object=Var(value="count"),
                    )
                ]
            )
        )

        # Rebuild the SELECT clause in the new SubSelect to retrieve the count of the focus node
        count_expression = Expression.from_primary_expr(
            PrimaryExpression(
                content=BuiltInCall(
                    other_expressions=Aggregate(
                        function_name="COUNT",
                        distinct=True,
                        expression=Expression.from_primary_expr(
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
