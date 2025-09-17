import logging

from rdflib.namespace import RDF
from sparql_grammar_pydantic import (
    IRI,
    DataBlock,
    DataBlockValue,
    GroupGraphPattern,
    GroupGraphPatternSub,
    InlineDataOneVar,
    SelectClause,
    SubSelect,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
    GraphPatternNotTriples,
    InlineData,
    SolutionModifier,
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
        select_clause = SelectClause(variables_or_all=[class_var, uris_var])
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    triples_block=TriplesBlock(
                        triples=TriplesSameSubjectPath.from_spo(
                            subject=uris_var,
                            predicate=IRI(value=RDF.type),
                            object=class_var,
                        )
                    ),
                    graph_patterns_or_triples_blocks=[
                        GraphPatternNotTriples(
                            content=InlineData(
                                data_block=DataBlock(
                                    block=InlineDataOneVar(
                                        variable=uris_var,
                                        datablockvalues=[
                                            DataBlockValue(value=uri) for uri in iris
                                        ],
                                    )
                                )
                            )
                        )
                    ],
                )
            )
        )
        super().__init__(
            select_clause=select_clause,
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )
