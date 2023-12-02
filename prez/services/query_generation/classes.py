import logging

from rdflib import URIRef
from rdflib.namespace import RDF

from temp.grammar import *

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
            uris: list[URIRef],
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

                    )
                )
            )
        )
        values_clause = ValuesClause(
            data_block=DataBlock(
                block=InlineDataOneVar(
                    variable=uris_var,
                    datablockvalues=[DataBlockValue(value=uri) for uri in uris],
                )
            )
        )
        super().__init__(
            select_clause=select_clause,
            where_clause=where_clause,
            values_clause=values_clause,
        )
