import logging

from rdflib.namespace import RDF
from sparql_grammar import (
    IRI,
    GroupGraphPattern,
    GroupGraphPatternSub,
    InlineData,
    InlineDataOneVar,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)

log = logging.getLogger(__name__)


class ClassesSelectQuery(SubSelect):
    """
    SELECT ?class ?uri
    WHERE {
        ?uri rdf:type ?class
        VALUES ?uri { <...> <...> }
    }
    """

    def __init__(
        self,
        iris: list[IRI],
    ):
        class_var = Var(value="class")
        uris_var = Var(value="uri")
        super().__init__(
            select_clause=SelectClause([class_var, uris_var]),
            where_clause=WhereClause(
                GroupGraphPattern(
                    GroupGraphPatternSub(
                        [
                            TriplesBlock(
                                [
                                    TriplesSameSubjectPath.from_spo(
                                        uris_var, IRI(value=RDF.type), class_var
                                    )
                                ]
                            ),
                            InlineData(InlineDataOneVar(uris_var, list(iris))),
                        ]
                    )
                )
            ),
            solution_modifier=SolutionModifier(),
        )
