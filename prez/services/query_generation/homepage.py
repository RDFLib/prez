from sparql_grammar import (
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
        url_var = Var(value="url")
        super().__init__(
            select_clause=SelectClause.create(url_var, distinct=True),
            where_clause=WhereClause(
                GroupGraphPattern(
                    GroupGraphPatternSub(
                        [
                            TriplesBlock(
                                [
                                    TriplesSameSubjectPath.from_spo(
                                        IRI(value=iri),
                                        IRI(value="http://xmlns.com/foaf/0.1/homepage"),
                                        url_var,
                                    )
                                ]
                            )
                        ]
                    )
                )
            ),
        )
