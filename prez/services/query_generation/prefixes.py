from sparql_grammar_pydantic import (
    IRI,
    GroupGraphPattern,
    GroupGraphPatternSub,
    SelectClause,
    SubSelect,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
    WhereClause, SolutionModifier, ValuesClause,
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
        select_clause = SelectClause(variables_or_all=[prefix_var, namespace_var])
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    triples_block=TriplesBlock.from_tssp_list(
                        [
                            TriplesSameSubjectPath.from_spo(
                                subject=subject_var,
                                predicate=IRI(
                                    value="http://purl.org/vocab/vann/preferredNamespacePrefix"
                                ),
                                object=prefix_var,
                            ),
                            TriplesSameSubjectPath.from_spo(
                                subject=subject_var,
                                predicate=IRI(
                                    value="http://purl.org/vocab/vann/preferredNamespaceUri"
                                ),
                                object=namespace_var,
                            ),
                        ]
                    )
                )
            )
        )
        super().__init__(
            select_clause=select_clause,
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )
