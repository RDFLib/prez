import logging
import sys

from rdflib import Namespace
from rdflib.namespace import RDF, RDFS
from sparql_grammar import (
    IRI,
    Bind,
    BuiltInCall,
    CollectionPath,
    ConstructQuery,
    ConstructTemplate,
    Expression,
    Filter,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitOffsetClauses,
    ObjectListPath,
    OrderClause,
    OrderCondition,
    PathAlternative,
    PropertyListPathNotEmpty,
    RDFLiteral,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
    numeric_literal,
)

from prez.reference_data.prez_ns import PREZ
from prez.services.query_generation.grammar_helpers import construct_triples
from prez.services.query_generation.search_default import hash_id_expression

logger = logging.getLogger(__name__)


class SearchQueryFusekiFTS(ConstructQuery):
    """Full-text search query generation for Fuseki FTS Index

    :param term: the seach term or phrase
    :param limit: sparql limit clause
    :param offset: sparql offset clause
    :param non_shacl_predicates: list of predicates to search over (must be indexed)
    :param shacl_tssp_preds: list of triples same subject paths, search predicates, and focus node classes
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
            list[
                tuple[
                    list[TriplesSameSubjectPath],
                    list[str],
                    list[str] | None,
                ]
            ]
            | None
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
            TriplesSameSubject.from_spo(hashid, p, v) for p, v in ct_map.items()
        ]

        if tss_list:
            construct_tss_list.extend(tss_list)

        construct_template = ConstructTemplate(construct_triples(construct_tss_list))

        def _generate_fts_triples_block(
            preds: list[str], sr_uri: Var = sr_uri
        ) -> TriplesBlock:
            # ( <pred1> <pred2> "term" [limit] ) - the argument list text:query takes
            arg_list = [IRI(value=predicate) for predicate in preds]
            arg_list.append(RDFLiteral(value=term))
            # Conditionally add FTS limit if configured
            if fts_limit is not None:
                arg_list.append(numeric_literal(fts_limit + offset))

            # (?focus_node ?weight ?match ?g ?pred) text:query ( ... )
            return TriplesBlock(
                [
                    TriplesSameSubjectPath(
                        CollectionPath([sr_uri, weight, match, g, pred]),
                        PropertyListPathNotEmpty(
                            [
                                (
                                    PathAlternative.iri(text_query),
                                    ObjectListPath.create(CollectionPath(arg_list)),
                                )
                            ]
                        ),
                    )
                ]
            )

        def _not_blank_filter(var: Var) -> Filter:
            """FILTER(!isBLANK(?var))"""
            return Filter(Expression.negate(BuiltInCall.create("isBLANK", var)))

        fts_search_node = Var(value="fts_search_node")

        def _dedupe_preserve_order(values: list[str]) -> list[str]:
            seen = set()
            out = []
            for v in values:
                if v in seen:
                    continue
                seen.add(v)
                out.append(v)
            return out

        def _is_iri_filter(var: Var) -> Filter:
            """FILTER(isIRI(?var))"""
            return Filter(
                Expression.from_primary_expression(BuiltInCall.create("isIRI", var))
            )

        def _bound_filter(var: Var) -> Filter:
            """FILTER(BOUND(?var))"""
            return Filter(
                Expression.from_primary_expression(BuiltInCall.create("BOUND", var))
            )

        def _subject_var_from_tssp(tssp: TriplesSameSubjectPath) -> Var | None:
            subj = tssp.subject
            return subj if isinstance(subj, Var) else None

        ggp_list = []
        if non_shacl_predicates:
            direct_preds = _dedupe_preserve_order(
                [str(p) for p in non_shacl_predicates]
            )
            if direct_preds:
                direct_text_query_tb = _generate_fts_triples_block(direct_preds, sr_uri)
                direct_preds_ggp = GroupGraphPattern(
                    GroupGraphPatternSub([direct_text_query_tb, _is_iri_filter(sr_uri)])
                )
                ggp_list.append(direct_preds_ggp)

        if shacl_tssp_preds:
            shacl_preds = []
            for _, preds, _ in shacl_tssp_preds:
                shacl_preds.extend([str(p) for p in preds])
            shacl_preds = _dedupe_preserve_order(shacl_preds)
            if shacl_preds:
                shacl_text_query_tb = _generate_fts_triples_block(
                    shacl_preds, fts_search_node
                )
                shacl_branch_ggps = []
                for tssp_list, preds, focus_node_classes in shacl_tssp_preds:
                    pred_values = _dedupe_preserve_order([str(p) for p in preds])
                    if not pred_values:
                        continue
                    branch_tssp_list = list(reversed(tssp_list))
                    branch_patterns = []
                    branch_patterns.append(_bound_filter(fts_search_node))
                    if not branch_tssp_list:
                        if focus_node_classes:
                            branch_patterns.append(
                                TriplesBlock(
                                    [
                                        TriplesSameSubjectPath.from_spo(
                                            fts_search_node,
                                            IRI(value=RDF.type),
                                            IRI(value=klass),
                                        )
                                        for klass in focus_node_classes
                                    ]
                                )
                            )
                        branch_patterns.append(
                            Bind(
                                Expression.from_primary_expression(fts_search_node),
                                sr_uri,
                            )
                        )
                        path_preds_ggp = GroupGraphPattern(
                            GroupGraphPatternSub(
                                [*branch_patterns, _not_blank_filter(sr_uri)]
                            )
                        )
                        shacl_branch_ggps.append(path_preds_ggp)
                        continue
                    seen_bound_vars = {fts_search_node.value}
                    for tssp in branch_tssp_list:
                        branch_patterns.append(TriplesBlock([tssp]))
                        subj_var = _subject_var_from_tssp(tssp)
                        if (
                            subj_var is not None
                            and subj_var.value != fts_search_node.value
                            and subj_var.value != sr_uri.value
                            and subj_var.value not in seen_bound_vars
                        ):
                            branch_patterns.append(_bound_filter(subj_var))
                            seen_bound_vars.add(subj_var.value)
                    path_preds_ggp = GroupGraphPattern(
                        GroupGraphPatternSub(
                            [
                                *branch_patterns,
                                _not_blank_filter(sr_uri),
                                *(
                                    [
                                        TriplesBlock(
                                            [
                                                TriplesSameSubjectPath.from_spo(
                                                    sr_uri,
                                                    IRI(value=RDF.type),
                                                    IRI(value=klass),
                                                )
                                                for klass in focus_node_classes or []
                                            ]
                                        )
                                    ]
                                    if focus_node_classes
                                    else []
                                ),
                            ]
                        )
                    )
                    shacl_branch_ggps.append(path_preds_ggp)
                if shacl_branch_ggps:
                    shacl_gpnt = GroupOrUnionGraphPattern(shacl_branch_ggps)
                    shacl_ggp = GroupGraphPattern(
                        GroupGraphPatternSub([shacl_text_query_tb, shacl_gpnt])
                    )
                    ggp_list.append(shacl_ggp)

        gpnt = GroupOrUnionGraphPattern(ggp_list)

        # SELECT ?focus_node ?predicate ?match ?weight (URI(CONCAT("urn:hash:",
        #   SHA256(CONCAT(STR(?focus_node), STR(?predicate), STR(?match), STR(?weight))))) AS ?hashID)
        where_clause = WhereClause(
            GroupGraphPattern(
                SubSelect(
                    select_clause=SelectClause(
                        [
                            sr_uri,
                            pred,
                            match,
                            weight,
                            (hash_id_expression(sr_uri, pred, match, weight), hashid),
                        ]
                    ),
                    where_clause=WhereClause(
                        GroupGraphPattern(GroupGraphPatternSub([gpnt]))
                    ),
                    solution_modifier=SolutionModifier(
                        order_by=OrderClause([OrderCondition.desc(weight)]),
                        limit_offset=LimitOffsetClauses.create(
                            limit=limit, offset=offset
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
    def _outer_subselect(self) -> SubSelect:
        return self.where_clause.group_graph_pattern.content

    @property
    def limit(self):
        return int(
            self._outer_subselect.solution_modifier.limit_offset.limit_clause.limit.value
        )

    @property
    def offset(self):
        return int(
            self._outer_subselect.solution_modifier.limit_offset.offset_clause.offset.value
        )

    @property
    def tss_list(self):
        return list(self.construct_template.construct_triples.triples)

    @property
    def inner_select_vars(self):
        return self._outer_subselect.select_clause.variables

    @property
    def inner_select_gpnt(self):
        inner_ggp = self._outer_subselect.where_clause.group_graph_pattern
        return GroupOrUnionGraphPattern([inner_ggp])


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
