import logging
import sys
from typing import Optional

from rdflib import Namespace
from rdflib.namespace import RDF, RDFS
from sparql_grammar_pydantic import (
    Constraint,
    Filter,
    BuiltInCall,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    LimitClause,
    LimitOffsetClauses,
    OffsetClause,
    OrderClause,
    OrderCondition,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesNodePath,
    TriplesSameSubject,
    WhereClause, IRI,
    Expression,
    GraphPatternNotTriples,
    PrimaryExpression,
    RDFLiteral,
    TriplesSameSubjectPath,
    Var,
    TriplesBlock,
    GroupGraphPattern,
    GroupGraphPatternSub,
    ServiceGraphPattern,
    VarOrIri,
    VarOrTerm,
    PropertyListPathNotEmpty,
    GraphTerm,
    VerbPath,
    SG_Path,
    PathAlternative,
    PathSequence,
    PathEltOrInverse,
    PathElt,
    PathPrimary,
    ObjectList,
    Object,
    GraphNode,
    GroupOrUnionGraphPattern,
    ObjectListPath,
    ObjectPath,
    GraphNodePath,
    BlankNodePropertyListPath
)

from prez.reference_data.prez_ns import PREZ

logger = logging.getLogger(__name__)


class SearchQueryQleverFTS(ConstructQuery):
    """Full-text search query generation for Qlever."""

    def __init__(
            self,
            term: str,
            limit: int,
            offset: int,
            predicates: Optional[list[str]] = None,
    ):
        limit += 1  # increase the limit by one, so we know if there are further pages of results.
        # join search terms with '+' for better results
        terms = set(term.split(" "))
        short_terms = {i for i in terms if len(i) <= 3}
        long_terms = terms - short_terms

        sr_uri: Var = Var(value="focus_node")
        weight: Var = Var(value="weight")
        match: Var = Var(value="match")
        pred: Var = Var(value="pred")
        hashid: Var = Var(value="hashID")
        _entity_score: Var = Var(value="entity_score")

        QLTS = Namespace("https://qlever.cs.uni-freiburg.de/textSearch/")
        TS_CONTAINS = IRI(value=QLTS.contains)
        TS_WORD = IRI(value=QLTS.word)
        TS_SCORE = IRI(value=QLTS.score)
        TS_ENTITY = IRI(value=QLTS.entity)

        def _verb_path_from_iri(iri: IRI):
            return VerbPath(
                path=SG_Path(
                    path_alternative=PathAlternative(
                        sequence_paths=[
                            PathSequence(
                                list_path_elt_or_inverse=[
                                    PathEltOrInverse(
                                        path_elt=PathElt(
                                            path_primary=PathPrimary(
                                                value=iri
                                            )
                                        )
                                    )
                                ]
                            )
                        ]
                    )
                )
            )

        def _olp_from_vot(vot: VarOrTerm):
            return ObjectListPath(
                object_paths=[
                    ObjectPath(
                        graph_node_path=GraphNodePath(
                            varorterm_or_triplesnodepath=vot
                        )
                    )
                ]
            )

        # add the longer search terms in this kind of pattern:
        # NB this pattern does NOT support search terms length <=3
        # these are separately handled in a filter only with FILTER CONTAINS, and therefore do NOT contribute to search
        # result scoring.
        """
        ?t textSearch:contains [
            textSearch:word "searchterm1" ;
            textSearch:score ?weight
        ] .
        ?t textSearch:contains [
            textSearch:word "searchterm2" ;
            textSearch:score ?weight
        ] .
        ?t textSearch:contains [
            textSearch:entity ?match ;
            textSearch:score ?entity_score
        ] .
        """
        qlever_service_gpnt = None
        if long_terms:
            match_vot = VarOrTerm(
                varorterm=match
            )
            long_term_vots = [
                VarOrTerm(
                    varorterm=GraphTerm(
                        content=RDFLiteral(
                            value=term
                        )
                    )
                ) for term in long_terms
            ]

            bnplp_args = [
                (TS_ENTITY, match_vot, _entity_score)
            ]
            for long_search_term in long_term_vots:
                bnplp_args.append(
                    (TS_WORD, long_search_term, weight)
                )
            tssp_list = []
            for bnplp_arg_set in bnplp_args:
                tssp_list.append(
                    TriplesSameSubjectPath(
                        content=(
                            VarOrTerm(
                                varorterm=Var(
                                    value="t"
                                )
                            ),
                            PropertyListPathNotEmpty(
                                first_pair=(
                                    _verb_path_from_iri(TS_CONTAINS),
                                    ObjectListPath(
                                        object_paths=[
                                            ObjectPath(
                                                graph_node_path=GraphNodePath(
                                                    varorterm_or_triplesnodepath=TriplesNodePath(
                                                        coll_path_or_bnpl_path=BlankNodePropertyListPath(
                                                            plpne=PropertyListPathNotEmpty(
                                                                first_pair=(
                                                                    _verb_path_from_iri(bnplp_arg_set[0]),
                                                                    _olp_from_vot(bnplp_arg_set[1])
                                                                ),
                                                                other_pairs=[
                                                                    (
                                                                        _verb_path_from_iri(TS_SCORE),
                                                                        ObjectList(
                                                                            list_object=[
                                                                                Object(
                                                                                    graphnode=GraphNode(
                                                                                        varorterm_or_triplesnode=VarOrTerm(
                                                                                            varorterm=bnplp_arg_set[2])
                                                                                    )
                                                                                )
                                                                            ]
                                                                        )
                                                                    )
                                                                ]
                                                            )
                                                        )
                                                    )
                                                )
                                            )
                                        ]
                                    )
                                )
                            )
                        )
                    )
                )
            tb = TriplesBlock.from_tssp_list(tssp_list)

            qlever_service_gpnt = GraphPatternNotTriples(
                content=ServiceGraphPattern(
                    var_or_iri=VarOrIri(
                        varoriri=IRI(
                            value=str(QLTS)
                        )
                    ),
                    group_graph_pattern=GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            graph_patterns_or_triples_blocks=[tb]
                        )
                    )
                )
            )

        # add the shorter search terms as filters only
        short_term_gpnts = []
        for term in short_terms:
            short_term_gpnts.append(
                GraphPatternNotTriples(
                    content=Filter(
                        constraint=Constraint(
                            content=BuiltInCall.create_with_n_expr(
                                "CONTAINS",
                                expressions=[
                                    PrimaryExpression(
                                        content=BuiltInCall.create_with_one_expr(
                                            "LCASE",
                                            PrimaryExpression(
                                                content=Var(value="match")
                                            )
                                        )
                                    ),
                                    PrimaryExpression(
                                        content=BuiltInCall.create_with_one_expr(
                                            "LCASE",
                                            PrimaryExpression(
                                                content=RDFLiteral(value=term)
                                            )
                                        )
                                    )
                                ],
                            )
                        )
                    )
                )
            )

        gpotb_list = [
            TriplesBlock.from_tssp_list(
                [
                    TriplesSameSubjectPath.from_spo(
                        subject=Var(value="focus_node"),
                        predicate=pred,
                        object=match
                    )
                ]
            )
        ]
        if qlever_service_gpnt:
            gpotb_list.append(qlever_service_gpnt)
        if short_term_gpnts:
            gpotb_list.extend(short_term_gpnts)


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

        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(construct_tss_list)
        )

        where_clause = WhereClause(
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
                                graph_patterns_or_triples_blocks=gpotb_list
                            )
                        )
                    ),
                    solution_modifier=SolutionModifier(
                        order_by=OrderClause(
                            conditions=[OrderCondition(constraint_or_var=weight, direction="DESC")]
                        ),
                        limit_offset=LimitOffsetClauses(
                            limit_clause=LimitClause(limit=limit),
                            offset_clause=OffsetClause(offset=offset),
                        ),
                    ),
                )
            )
        )
        super().__init__(
            construct_template=construct_template,
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )


    @property


    def order_by_val(self):
        return Var(value="weight")


    @property
    def order_by_direction(self):
        return "DESC"


    @property
    def limit(self):
        return (
            self.where_clause.group_graph_pattern.content.solution_modifier.limit_offset.limit_clause.limit
        )


    @property
    def offset(self):
        return (
            self.where_clause.group_graph_pattern.content.solution_modifier.limit_offset.offset_clause.offset
        )


    @property
    def tss_list(self):
        return self.construct_template.construct_triples.to_tss_list()


    @property
    def inner_select_vars(self):
        return (
            self.where_clause.group_graph_pattern.content.select_clause.variables_or_all
        )


    @property
    def inner_select_gpnt(self):
        inner_ggp = (
            self.where_clause.group_graph_pattern.content.where_clause.group_graph_pattern
        )
        return GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(group_graph_patterns=[inner_ggp])
        )


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    fts_query = SearchQueryQleverFTS(
        term="test",
        limit=10,
        offset=0,
        predicates=[RDFS.label, RDFS.comment],
    )
    logger.debug(fts_query)
