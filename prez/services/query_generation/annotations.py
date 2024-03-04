from typing import List

from temp.grammar import *


class AnnotationsConstructQuery(ConstructQuery):
    def __init__(
        self, term: IRI, construct_predicate: IRI, select_predicates: List[IRI]
    ):
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples(
                triples=[
                    SimplifiedTriple(
                        subject=term,
                        predicate=construct_predicate,
                        object=Var(value="annotation"),
                    )
                ]
            )
        )
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[
                        TriplesBlock(
                            triples=[
                                SimplifiedTriple(
                                    subject=term,
                                    predicate=select_predicates[
                                        0
                                    ],  # Assuming a single select predicate for simplicity
                                    object=Var(value="annotation"),
                                )
                            ]
                        )
                    ]
                )
            )
        )
        solution_modifier = SolutionModifier()
        super().__init__(
            construct_template=construct_template,
            where_clause=where_clause,
            solution_modifier=solution_modifier,
        )
