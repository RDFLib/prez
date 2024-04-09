import logging

from rdflib import URIRef
from rdflib.namespace import RDF
from typing import Optional
from temp.grammar import *

log = logging.getLogger(__name__)


# async def get_classes(uri: URIRef, repo: Repo) -> frozenset[URIRef]:
#     """
#     Generates a query of the form:
#     SELECT ?class WHERE { <uri> rdf:type ?class }
#     """
#     query = SubSelect(
#         select_clause=SelectClause(variables_or_all=[Var(value="class")]),
#         where_clause=WhereClause(
#             group_graph_pattern=GroupGraphPattern(
#                 content=GroupGraphPatternSub(
#                     triples_block=TriplesBlock(
#                         triples=[
#                             SimplifiedTriple(
#                                 subject=IRI(value=uri),
#                                 predicate=IRI(value=RDF.type),
#                                 object=Var(value="class"),
#                             )
#                         ]
#                     )
#                 )
#             )
#         ),
#     ).to_string()
#     _, r = await repo.send_queries([], [(uri, query)])
#     tabular_result = r[0]  # should only be one result - only one query sent
#     classes = frozenset([URIRef(c["class"]["value"]) for c in tabular_result[1]])
#     return classes


class ClassesSelectQuery(SubSelect):
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
                        triples=[
                            SimplifiedTriple(
                                subject=uris_var,
                                predicate=IRI(value=RDF.type),
                                object=class_var,
                            )
                        ]
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
