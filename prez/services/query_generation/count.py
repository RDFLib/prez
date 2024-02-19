from pydantic import BaseModel
from rdflib import RDF, BNode

from prez.reference_data.prez_ns import PREZ
from temp.grammar import *


class CountQuery(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    subselect: SubSelect

    def render(self):
        cq = self.create_construct_query()
        return "".join(part for part in cq.render())

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


def startup_count_objects():
    """
    Retrieves hardcoded counts for collections in the repository (Feature Collections, Catalogs etc.)
    """
    return f"""PREFIX prez: <https://prez.dev/>
                CONSTRUCT {{ ?collection prez:count ?count }}
                WHERE {{ ?collection prez:count ?count }}"""
