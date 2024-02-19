import logging
from rdflib import URIRef
from rdflib.namespace import RDF

from prez.repositories import Repo
from temp.grammar import (
    SelectClause,
    Var,
    SubSelect,
    WhereClause,
    GroupGraphPattern,
    GroupGraphPatternSub,
    TriplesBlock,
    SimplifiedTriple,
    IRI,
)

log = logging.getLogger(__name__)


async def get_classes(uri: URIRef, repo: Repo) -> frozenset[URIRef]:
    """
    Generates a query of the form:
    SELECT ?class WHERE { <uri> rdf:type ?class }
    """
    query = SubSelect(
        select_clause=SelectClause(variables_or_all=[Var(value="class")]),
        where_clause=WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    triples_block=TriplesBlock(
                        triples=[
                            SimplifiedTriple(
                                subject=IRI(value=uri),
                                predicate=IRI(value=RDF.type),
                                object=Var(value="class"),
                            )
                        ]
                    )
                )
            )
        ),
    ).to_string()
    _, r = await repo.send_queries([], [(uri, query)])
    tabular_result = r[0]  # should only be one result - only one query sent
    classes = frozenset([URIRef(c["class"]["value"]) for c in tabular_result[1]])
    return classes
