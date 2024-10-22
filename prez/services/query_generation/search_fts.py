import logging
import sys

from rdflib import Namespace
from rdflib.namespace import RDF, RDFS
from sparql_grammar_pydantic import (
    IRI,
    BuiltInCall,
    CollectionPath,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    GraphNodePath,
    GraphPatternNotTriples,
    GraphTerm,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitClause,
    LimitOffsetClauses,
    ObjectListPath,
    ObjectPath,
    OffsetClause,
    OrderClause,
    OrderCondition,
    PathAlternative,
    PathElt,
    PathEltOrInverse,
    PathPrimary,
    PathSequence,
    PrimaryExpression,
    PropertyListPath,
    PropertyListPathNotEmpty,
    RDFLiteral,
    SelectClause,
    SG_Path,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesNodePath,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    VarOrTerm,
    VerbPath,
    WhereClause,
)

from prez.config import settings
from prez.reference_data.prez_ns import PREZ

logger = logging.getLogger(__name__)


class SearchQueryFusekiFTS:
    """Full-text search query generation for Fuseki FTS Index

    :param term: the seach term or phrase
    :param limit: sparql limit clause
    :param offset: sparql offset clause
    :param predicates: list of predicates to search over (must be indexed)

    generates a query of the form

    .. code:: sparql

        construct {
            ?hashID <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://prez.dev/SearchResult> .
            ?hashID <https://prez.dev/searchResultURI> ?focus_node .
            ?hashID <https://prez.dev/searchResultMatch> ?match .
            ?hashID <https://prez.dev/searchResultPredicate> ?pred .
            ?hashID <https://prez.dev/searchResultWeight> ?weight
        }
        where {
            select ?focus_node ?pred ?match ?weight (URI(CONCAT("urn:hash:", SHA256(CONCAT(STR(?focus_node), STR(?pred), STR(?match), STR(?weight))))) as ?hashID)
            where {
                (?focus_node ?weight ?match ?g ?pred) text:query ( <search_predicates> "<search_term>")
            }
        }
        order by desc(?weight)
        limit <limit>
        offset <offset>

    NOTE:
        By default the search phrase given by `term` will be split by whitespace and concatenated together with '+' as this
        gives better results in most scenarios.

    """

    def __init__(
        self,
        term: str,
        limit: int,
        offset: int,
        predicates: list[str] | None = None,
    ):
        limit += 1  # increase the limit by one, so we know if there are further pages of results.
        # join search terms with '+' for better results
        term = "+".join(term.split(" "))

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

        self.query = ConstructQuery(
            construct_template=ConstructTemplate(
                construct_triples=ConstructTriples.from_tss_list(construct_tss_list)
            ),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(
                    content=SubSelect(
                        # SELECT ?focus_node ?predicate ?match ?weight (URI(CONCAT("urn:hash:",
                        #   SHA256(CONCAT(STR(?focus_node), STR(?predicate), STR(?match), STR(?weight))))) AS ?hashID)
                        select_clause=SelectClause(
                            variables_or_all=[
                                sr_uri,
                                pred,
                                match,
                                weight,
                                (
                                    Expression.from_primary_expression(
                                        PrimaryExpression(
                                            content=BuiltInCall.create_with_one_expr(
                                                "URI",
                                                PrimaryExpression(
                                                    content=BuiltInCall.create_with_n_expr(
                                                        "CONCAT",
                                                        [
                                                            PrimaryExpression(
                                                                content=RDFLiteral(
                                                                    value="urn:hash:"
                                                                )
                                                            ),
                                                            PrimaryExpression(
                                                                content=BuiltInCall.create_with_one_expr(
                                                                    "SHA256",
                                                                    PrimaryExpression(
                                                                        content=BuiltInCall.create_with_n_expr(
                                                                            "CONCAT",
                                                                            [
                                                                                PrimaryExpression(
                                                                                    content=b
                                                                                )
                                                                                for b in [
                                                                                    BuiltInCall.create_with_one_expr(
                                                                                        "STR",
                                                                                        PrimaryExpression(
                                                                                            content=e
                                                                                        ),
                                                                                    )
                                                                                    for e in [
                                                                                        sr_uri,
                                                                                        pred,
                                                                                        match,
                                                                                        weight,
                                                                                    ]
                                                                                ]
                                                                            ],
                                                                        )
                                                                    ),
                                                                )
                                                            ),
                                                        ],
                                                    )
                                                ),
                                            )
                                        )
                                    ),
                                    hashid,
                                ),
                            ]
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
                                                            ObjectListPath(
                                                                object_paths=[
                                                                    ObjectPath(
                                                                        graph_node_path=GraphNodePath(
                                                                            varorterm_or_triplesnodepath=TriplesNodePath(
                                                                                coll_path_or_bnpl_path=CollectionPath(
                                                                                    graphnodepath_list=[
                                                                                        GraphNodePath(
                                                                                            varorterm_or_triplesnodepath=VarOrTerm(
                                                                                                varorterm=GraphTerm(
                                                                                                    content=IRI(
                                                                                                        value=predicate
                                                                                                    )
                                                                                                )
                                                                                            )
                                                                                        )
                                                                                        for predicate in predicates
                                                                                    ]
                                                                                    + [
                                                                                        GraphNodePath(
                                                                                            varorterm_or_triplesnodepath=VarOrTerm(
                                                                                                varorterm=GraphTerm(
                                                                                                    content=RDFLiteral(
                                                                                                        value=term
                                                                                                    )
                                                                                                )
                                                                                            )
                                                                                        )
                                                                                    ]
                                                                                )
                                                                            )
                                                                        )
                                                                    )
                                                                ]
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
                    )
                )
            ),
            solution_modifier=SolutionModifier(
                order_by=OrderClause(
                    conditions=[OrderCondition(var=weight, direction="DESC")]
                ),
                limit_offset=LimitOffsetClauses(
                    limit_clause=LimitClause(limit=limit),
                    offset_clause=OffsetClause(offset=offset),
                ),
            ),
        )
        logger.debug(f"constructed Fuseki FTS query:\n{self.query}")

    @property
    def order_by(self):
        return Var(value="weight")

    @property
    def order_by_direction(self):
        return "DESC"

    @property
    def limit(self):
        return self.query.solution_modifier.limit_offset.limit_clause.limit

    @property
    def offset(self):
        return self.query.solution_modifier.limit_offset.offset_clause.offset

    @property
    def tss_list(self):
        return self.query.construct_template.construct_triples.to_tss_list()

    @property
    def inner_select_vars(self):
        return (
            self.query.where_clause.group_graph_pattern.content.select_clause.variables_or_all
        )

    @property
    def inner_select_gpnt(self):
        inner_ggp = (
            self.query.where_clause.group_graph_pattern.content.where_clause.group_graph_pattern
        )
        return GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(group_graph_patterns=[inner_ggp])
        )


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    fts_query = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        predicates=[RDFS.label, RDFS.comment],
    )
