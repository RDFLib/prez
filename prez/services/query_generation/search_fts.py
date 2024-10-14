import logging

from rdflib import Namespace
from rdflib.namespace import RDF, RDFS
from sparql_grammar_pydantic import (IRI, CollectionPath, ConstructQuery,
                                     ConstructTemplate, ConstructTriples,
                                     GraphNodePath, GraphTerm,
                                     GroupGraphPattern, GroupGraphPatternSub,
                                     ObjectListPath, ObjectPath,
                                     PathAlternative, PathElt,
                                     PathEltOrInverse, PathPrimary,
                                     PathSequence, PropertyListPath,
                                     PropertyListPathNotEmpty, SG_Path,
                                     SolutionModifier, TriplesBlock,
                                     TriplesNodePath, TriplesSameSubject,
                                     TriplesSameSubjectPath, Var, VarOrTerm,
                                     VerbPath, WhereClause)

from prez.config import settings
from prez.reference_data.prez_ns import PREZ

logger = logging.getLogger(__name__)


class SearchQueryFusekiFTS:
    """Full text search query generation for Fuseki FTS Index

    generates a query of the form

        select ?focus_node ?weight ?match ?g ?pred
        where {
            (?focus_node ?weight ?match ?g ?pred) text:query ( <search_predicates> "<search_term>")
        }
    """

    def __init__(
        self,
        term: str,
        limit: int,
        offset: int,
        predicates: list[str] = None,
    ):

        limit += 1  # increase the limit by one so we know if there are further pages of results.

        sr_uri: Var = Var(value="focus_node")
        weight: Var = Var(value="weight")
        match: Var = Var(value="match")
        g: Var = Var(value="g")
        pred: Var = Var(value="pred")
        hashid: Var = Var(value="hashID")

        TEXT = Namespace("http://jena.apache.org/text#")
        text_query: IRI = IRI(value=TEXT.query)

        if not predicates:
            predicates = settings.search_predicates

        ct_map = {
            IRI(value=PREZ.searchResultWeight): weight,
            IRI(value=PREZ.searchResultPredicate): pred,
            IRI(value=PREZ.searchResultMatch): match,
            IRI(value=PREZ.searchResultURI): sr_uri,
            IRI(value=RDF.type): IRI(value=PREZ.SearchResult),
        }

        # set construct triples
        construct_tss_list = [
            TriplesSameSubject.from_spo(subject=hashid, predicate=p, object=v)
            for p, v in ct_map.items()
        ]

        query = ConstructQuery(
            construct_template=ConstructTemplate(
                construct_triples=ConstructTriples.from_tss_list(construct_tss_list)
            ),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        triples_block=TriplesBlock(
                            triples=TriplesSameSubjectPath(
                                content=(
                                    TriplesNodePath(
                                        coll_path_or_bnpl_path=CollectionPath(
                                            graphnodepath_list=[
                                                GraphNodePath(
                                                    varorterm_or_triplesnodepath=VarOrTerm(
                                                        varorterm=sr_uri
                                                    )
                                                ),
                                                GraphNodePath(
                                                    varorterm_or_triplesnodepath=VarOrTerm(
                                                        varorterm=weight
                                                    )
                                                ),
                                                GraphNodePath(
                                                    varorterm_or_triplesnodepath=VarOrTerm(
                                                        varorterm=match
                                                    )
                                                ),
                                                GraphNodePath(
                                                    varorterm_or_triplesnodepath=VarOrTerm(
                                                        varorterm=g
                                                    )
                                                ),
                                                GraphNodePath(
                                                    varorterm_or_triplesnodepath=VarOrTerm(
                                                        varorterm=pred
                                                    )
                                                ),
                                            ]
                                        )
                                    ),
                                    PropertyListPath(
                                        plpne=PropertyListPathNotEmpty(
                                            first_pair=(
                                                VerbPath(
                                                    path=SG_Path(
                                                        path_alternative=PathAlternative(
                                                            sequence_paths=[
                                                                PathSequence(
                                                                    list_path_elt_or_inverse=[
                                                                        PathEltOrInverse(
                                                                            path_elt=PathElt(
                                                                                path_primary=PathPrimary(
                                                                                    value=text_query
                                                                                )
                                                                            )
                                                                        )
                                                                    ]
                                                                )
                                                            ]
                                                        )
                                                    )
                                                ),
                                                # TODO: finish implementation
                                                ObjectListPath(
                                                    object_paths=[ObjectPath(
                                                        graph_node_path=GraphNodePath(
                                                            varorterm_or_triplesnodepath=VarOrTerm(
                                                                varorterm=GraphTerm(
                                                                    content=IRI(
                                                                        value=RDFS.label
                                                                    )
                                                                )
                                                            )
                                                        )
                                                    )]
                                                ),
                                            )
                                        )
                                    ),
                                )
                            )
                        )
                    )
                )
            ),
            solution_modifier=SolutionModifier(),
        )
        logger.debug(f"constructed Fuseki FTS query:\n{query}")

    @property
    def order_by(self):
        return Var(value="weight")

    @property
    def order_by_direction(self):
        return "DESC"

    @property
    def limit(self):
        return self.limit

    @property
    def offset(self):
        return self.offset


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    fts_query = SearchQueryFusekiFTS(
        term="test", limit=10, offset=0, predicates=[IRI(value=RDFS.label)]
    )
