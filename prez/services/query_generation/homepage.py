from sparql_grammar_pydantic import (
    IRI,
    GroupGraphPattern,
    GroupGraphPatternSub,
    SelectClause,
    SubSelect,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)


class FoafHomepageQuery(SubSelect):
    """
    SELECT DISTINCT ?url
    WHERE {
        <{{ iri }}> foaf:homepage ?url .
    }
    """

    def __init__(self, iri: str):
        iri_var = IRI(value=iri)
        url_var = Var(value="url")
        select_clause = SelectClause(distinct=True, variables_or_all=[url_var])
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    triples_block=TriplesBlock(
                        triples=TriplesSameSubjectPath.from_spo(
                            subject=iri_var,
                            predicate=IRI(value="http://xmlns.com/foaf/0.1/homepage"),
                            object=url_var,
                        )
                    )
                )
            )
        )
        super().__init__(
            select_clause=select_clause,
            where_clause=where_clause,
        )
