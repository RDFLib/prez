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
        self.remove_limit_and_offset()
        self.rebuild_select_clause()
        cq = ConstructQuery(
            construct_template=self.create_construct_template(),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(
                    content=self.subselect
                )
            ),
            solution_modifier=SolutionModifier()
        )
        return cq

    def remove_limit_and_offset(self):
        self.subselect.solution_modifier = None

    def rebuild_select_clause(self):
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
                                            content=Var(
                                                value="focus_node")
                                        )
                                    )
                                )
                            )
                        )
                    ),
                    Var(value="count")
                )
            ]
        )
        self.subselect.select_clause = sc

    def create_construct_template(self):
        """
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
