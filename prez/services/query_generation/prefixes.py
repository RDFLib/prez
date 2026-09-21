from sparql_grammar import (
    IRI,
    GroupGraphPattern,
    GroupGraphPatternSub,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)


class PrefixQuery(SubSelect):
    """
    SELECT ?prefix ?namespace
    WHERE {
        ?subject vann:preferredNamespacePrefix ?prefix ;
                 vann:preferredNamespaceUri ?namespace .
    }
    """

    def __init__(self):
        prefix_var = Var(value="prefix")
        namespace_var = Var(value="namespace")
        subject_var = Var(value="subject")
        super().__init__(
            select_clause=SelectClause([prefix_var, namespace_var]),
            where_clause=WhereClause(
                GroupGraphPattern(
                    GroupGraphPatternSub(
                        [
                            TriplesBlock(
                                [
                                    TriplesSameSubjectPath.from_spo(
                                        subject_var,
                                        IRI(
                                            value="http://purl.org/vocab/vann/preferredNamespacePrefix"
                                        ),
                                        prefix_var,
                                    ),
                                    TriplesSameSubjectPath.from_spo(
                                        subject_var,
                                        IRI(
                                            value="http://purl.org/vocab/vann/preferredNamespaceUri"
                                        ),
                                        namespace_var,
                                    ),
                                ]
                            )
                        ]
                    )
                )
            ),
            solution_modifier=SolutionModifier(),
        )
