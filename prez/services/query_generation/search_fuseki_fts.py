import logging
import sys

from rdflib import Namespace
from rdflib.namespace import RDF, RDFS
from sparql_grammar_pydantic import (
    IRI,
    AdditiveExpression,
    BrackettedExpression,
    BuiltInCall,
    CollectionPath,
    ConditionalAndExpression,
    ConditionalOrExpression,
    Constraint,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    Filter,
    GraphNodePath,
    GraphPatternNotTriples,
    GraphTerm,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitClause,
    LimitOffsetClauses,
    MultiplicativeExpression,
    NumericExpression,
    NumericLiteral,
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
    RelationalExpression,
    SelectClause,
    SG_Path,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesNodePath,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    UnaryExpression,
    ValueLogical,
    Var,
    VarOrTerm,
    VerbPath,
    WhereClause,
)

from prez.reference_data.prez_ns import PREZ

logger = logging.getLogger(__name__)


class SearchQueryFusekiFTS(ConstructQuery):
    """Full-text search query generation for Fuseki FTS Index

    :param term: the seach term or phrase
    :param limit: sparql limit clause
    :param offset: sparql offset clause
    :param non_shacl_predicates: list of predicates to search over (must be indexed)
    :param shacl_tssp_preds: list of triples same subject paths and search predicate
                             (typically generated from a <https://prez.dev/ont/JenaFTSPropertyShape>)
    :param tss_list: list of triples same subject paths
                     (typically generated from a <https://prez.dev/ont/JenaFTSPropertyShape>)

    generates a query of the form

    .. code:: sparql

        CONSTRUCT {
            ?prof_101_node_1 <http://www.w3.org/ns/sosa/hasResult> ?fts_search_node .
            ?focus_node <http://www.w3.org/ns/sosa/isFeatureOfInterestOf> ?prof_101_node_1 .
            ?hashID <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://prez.dev/SearchResult> .
            ?hashID <https://prez.dev/searchResultURI> ?focus_node .
            ?hashID <https://prez.dev/searchResultMatch> ?match .
            ?hashID <https://prez.dev/searchResultPredicate> ?pred .
            ?hashID <https://prez.dev/searchResultWeight> ?weight
        }
        WHERE {
            SELECT ?focus_node ?pred ?match ?weight (URI(CONCAT("urn:hash:", SHA256(CONCAT(STR(?focus_node), STR(?pred), STR(?match), STR(?weight))))) AS ?hashID)
            WHERE {
                {
                    (?focus_node ?weight ?match ?g ?pred) <http://jena.apache.org/text#query> ( <searchProp1> <searchProp2> "search+term" <limit>)
                }
                UNION
                {
                    (?fts_search_node ?weight ?match ?g ?pred) <http://jena.apache.org/text#query> (<shaclSearchProp> "search+term") .
                    ?prof_101_node_1 <shaclPathPart1> ?fts_search_node .
                    ?focus_node <shaclPathPart2> ?prof_101_node_1
                }
            }
            ORDER BY DESC( ?weight )
            LIMIT <limit>
            OFFSET <offset>
        }

    NOTE:
        By default the search phrase given by `term` will be split by whitespace and concatenated together with '+' as this
        gives better results in most scenarios.

    """

    def __init__(
        self,
        term: str,
        limit: int,
        offset: int,
        non_shacl_predicates: list[str] | None = None,
        shacl_tssp_preds: (
            list[tuple[list[TriplesSameSubjectPath], list[str]]] | None
        ) = None,
        tss_list: list[TriplesSameSubjectPath] | None = None,
        fts_limit: int | None = None,
    ):
        if not any([bool(non_shacl_predicates), bool(shacl_tssp_preds)]):
            raise ValueError(
                "At least one of `non_shacl_predicates` and `shacl_tssp_preds` must be given"
            )
        limit += 1  # increase the limit by one, so we know if there are further pages of results.
        # clients submitting lucene FTS queries must escape the following characters if they do not want them to have
        # the lucene special meaning: + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
        term = term.replace(
            "\\", "\\\\"
        )  # escape for SPARQL anything that has been Lucene escaped already
        term = term.replace('"', '\\"')  # escape quotes for SPARQL

        sr_uri: Var = Var(value="focus_node")
        weight: Var = Var(value="weight")
        match: Var = Var(value="match")
        g: Var = Var(value="g")
        pred: Var = Var(value="pred")
        hashid: Var = Var(value="hashID")

        TEXT = Namespace("http://jena.apache.org/text#")
        text_query: IRI = IRI(value=TEXT.query)

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

        if tss_list:
            construct_tss_list.extend(tss_list)

        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(construct_tss_list)
        )

        def _generate_fts_triples_block(
            preds: list[str], sr_uri: Var = sr_uri
        ) -> TriplesBlock:
            # Build base graphnodepath_list with predicates and search term
            base_list = [
                GraphNodePath(
                    varorterm_or_triplesnodepath=VarOrTerm(
                        varorterm=GraphTerm(content=IRI(value=predicate))
                    )
                )
                for predicate in preds
            ] + [
                GraphNodePath(
                    varorterm_or_triplesnodepath=VarOrTerm(
                        varorterm=GraphTerm(content=RDFLiteral(value=term))
                    )
                )
            ]

            # Conditionally add FTS limit if configured
            if fts_limit is not None:
                base_list.append(
                    GraphNodePath(
                        varorterm_or_triplesnodepath=VarOrTerm(
                            varorterm=GraphTerm(content=NumericLiteral(value=fts_limit + offset))
                        )
                    )
                )

            return TriplesBlock(
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
                                                            graphnodepath_list=base_list
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

        ggp_list = []
        bnode_filter = Filter(
            constraint=Constraint(
                content=BrackettedExpression(
                    expression=Expression(
                        conditional_or_expression=ConditionalOrExpression(
                            conditional_and_expressions=[
                                ConditionalAndExpression(
                                    value_logicals=[
                                        ValueLogical(
                                            relational_expression=RelationalExpression(
                                                left=NumericExpression(
                                                    additive_expression=AdditiveExpression(
                                                        base_expression=MultiplicativeExpression(
                                                            base_expression=UnaryExpression(
                                                                operator="!",
                                                                primary_expression=PrimaryExpression(
                                                                    content=BuiltInCall(
                                                                        function_name="isBLANK",
                                                                        arguments=[
                                                                            sr_uri
                                                                        ],
                                                                    )
                                                                ),
                                                            )
                                                        )
                                                    )
                                                )
                                            )
                                        )
                                    ]
                                )
                            ]
                        )
                    )
                )
            )
        )
        if non_shacl_predicates:
            direct_preds_tb = _generate_fts_triples_block(non_shacl_predicates)
            direct_preds_ggp = GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[
                        direct_preds_tb,
                        GraphPatternNotTriples(content=bnode_filter),
                    ]
                )
            )
            ggp_list.append(direct_preds_ggp)
        if shacl_tssp_preds:
            for tssp_list, preds in shacl_tssp_preds:
                path_preds_tb = _generate_fts_triples_block(
                    preds, Var(value="fts_search_node")
                )
                path_preds_tb.triples_block = TriplesBlock.from_tssp_list(tssp_list)
                path_preds_ggp = GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        graph_patterns_or_triples_blocks=[
                            path_preds_tb,
                            GraphPatternNotTriples(content=bnode_filter),
                        ]
                    )
                )
                ggp_list.append(path_preds_ggp)

        gpnt = GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(group_graph_patterns=ggp_list)
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
                                graph_patterns_or_triples_blocks=[gpnt]
                            )
                        )
                    ),
                    solution_modifier=SolutionModifier(
                        order_by=OrderClause(
                            conditions=[
                                OrderCondition(
                                    constraint_or_var=weight, direction="DESC"
                                )
                            ]
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
    fts_query = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        non_shacl_predicates=[RDFS.label, RDFS.comment],
    )
    logger.debug(fts_query)
