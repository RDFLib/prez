import json

from rdflib import RDF, Namespace
from sparql_grammar_pydantic import (
    IRI,
    AdditiveExpression,
    BrackettedExpression,
    BuiltInCall,
    CollectionPath,
    ConditionalAndExpression,
    ConditionalOrExpression,
    Constraint,
    Expression,
    Filter,
    GraphNodePath,
    GraphPatternNotTriples,
    GraphTerm,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    MultiplicativeExpression,
    NumericExpression,
    NumericLiteral,
    ObjectListPath,
    ObjectPath,
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
    SG_Path,
    TriplesBlock,
    TriplesNodePath,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    UnaryExpression,
    ValueLogical,
    Var,
    VarOrTerm,
    VerbPath,
)

from prez.reference_data.prez_ns import PREZ


LUCENE = Namespace("urn:jena:lucene:index#")


def _sparql_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _compact_json(value: dict | list | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class LuceneFacetQuery:
    def __init__(
        self,
        term: str | None,
        facets: list[str],
        limit: int,
        lucene_index_name: str,
        filter_json: dict | None = None,
    ):
        self._term = "*" if term is None else term
        self._facets = facets
        self._limit = limit
        self._lucene_index_name = lucene_index_name
        self._filter_json = filter_json

    def to_string(self) -> str:
        lucene_args = [
            _sparql_string_literal(self._lucene_index_name),
            _sparql_string_literal(self._term),
            _sparql_string_literal(_compact_json(self._facets)),
        ]
        compact_filter_json = _compact_json(self._filter_json)
        if compact_filter_json is not None:
            lucene_args.append(_sparql_string_literal(compact_filter_json))
        lucene_args.append(str(self._limit))
        return f"""CONSTRUCT {{
[] <{PREZ.facetName}> ?facetName ;
   <{PREZ.facetValue}> ?facetValue ;
   <{PREZ.facetCount}> ?facetCount .
}}
WHERE {{
{{
SELECT ?facetName ?facetValue ?facetCount
WHERE {{
(?facetName ?facetValue ?facetCount) <{LUCENE.facet}> ({' '.join(lucene_args)}) .
}}
}}
}}"""


class SearchQueryJenaLucene:
    def __init__(
        self,
        term: str | None,
        limit: int,
        offset: int,
        lucene_index_name: str,
        filter_json: dict | None = None,
    ):
        self._limit = limit + 1
        self._lucene_limit = self._limit + offset
        self._offset = offset
        self._lucene_index_name = lucene_index_name
        self._term = "*" if term is None else term
        self._filter_json = filter_json

        sr_uri = Var(value="focus_node")
        weight = Var(value="weight")
        match = Var(value="match")
        total_hits = Var(value="totalHits")
        pred = Var(value="pred")
        hashid = Var(value="hashID")

        ct_map = {
            IRI(value=PREZ.searchResultWeight): weight,
            IRI(value=PREZ.searchResultPredicate): pred,
            IRI(value=PREZ.searchResultMatch): match,
            IRI(value=PREZ.searchResultURI): sr_uri,
            IRI(value=RDF.type): IRI(value=PREZ.SearchResult),
        }
        self._tss_list = [
            TriplesSameSubject.from_spo(subject=hashid, predicate=p, object=v)
            for p, v in ct_map.items()
        ]
        self._tss_list.append(
            TriplesSameSubject.from_spo(
                subject=IRI(value=PREZ.SearchResult),
                predicate=IRI(value=PREZ["count"]),
                object=total_hits,
            )
        )
        self._inner_select_vars = [
            sr_uri,
            pred,
            match,
            weight,
            total_hits,
            (self._create_hashid_expression(sr_uri, pred, match, weight), hashid),
        ]
        self._inner_select_gpnt = self._build_inner_select_gpnt(
            sr_uri=sr_uri,
            weight=weight,
            match=match,
            total_hits=total_hits,
            pred=pred,
            lucene_index_name=lucene_index_name,
        )

    def _compact_filter_json(self) -> str | None:
        return _compact_json(self._filter_json)

    def _create_hashid_expression(
        self,
        sr_uri: Var,
        pred: Var,
        match: Var,
        weight: Var,
    ) -> Expression:
        return Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall.create_with_one_expr(
                    "URI",
                    PrimaryExpression(
                        content=BuiltInCall.create_with_n_expr(
                            "CONCAT",
                            [
                                PrimaryExpression(content=RDFLiteral(value="urn:hash:")),
                                PrimaryExpression(
                                    content=BuiltInCall.create_with_one_expr(
                                        "SHA256",
                                        PrimaryExpression(
                                            content=BuiltInCall.create_with_n_expr(
                                                "CONCAT",
                                                [
                                                    PrimaryExpression(content=b)
                                                    for b in [
                                                        BuiltInCall.create_with_one_expr(
                                                            "STR",
                                                            PrimaryExpression(content=e),
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
        )

    def _build_is_iri_filter(self, var: Var) -> Filter:
        return Filter(
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
                                                                primary_expression=PrimaryExpression(
                                                                    content=BuiltInCall(
                                                                        function_name="isIRI",
                                                                        arguments=[var],
                                                                    )
                                                                )
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

    def _build_inner_select_gpnt(
        self,
        sr_uri: Var,
        weight: Var,
        match: Var,
        total_hits: Var,
        pred: Var,
        lucene_index_name: str,
    ) -> GraphPatternNotTriples:
        query_var = Var(value="g")
        lucene_args = [
            GraphNodePath(
                varorterm_or_triplesnodepath=VarOrTerm(
                    varorterm=GraphTerm(content=RDFLiteral(value=lucene_index_name))
                )
            ),
            GraphNodePath(
                varorterm_or_triplesnodepath=VarOrTerm(
                    varorterm=GraphTerm(content=RDFLiteral(value=self._term))
                )
            ),
        ]
        if self._filter_json is not None:
            lucene_args.append(
                GraphNodePath(
                    varorterm_or_triplesnodepath=VarOrTerm(
                        varorterm=GraphTerm(
                            content=RDFLiteral(
                                value=json.dumps(
                                    self._filter_json,
                                    separators=(",", ":"),
                                    ensure_ascii=False,
                                )
                            )
                        )
                    )
                )
            )
        lucene_args.append(
            GraphNodePath(
                varorterm_or_triplesnodepath=VarOrTerm(
                    varorterm=GraphTerm(
                        content=NumericLiteral(value=self._lucene_limit)
                    )
                )
            )
        )

        lucene_query_tb = TriplesBlock(
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
                                        varorterm=total_hits
                                    )
                                ),
                                GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=query_var
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
                                                                    value=IRI(
                                                                        value=LUCENE.query
                                                                    )
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
                                                        graphnodepath_list=lucene_args
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

        inner_ggp = GroupGraphPattern(
            content=GroupGraphPatternSub(
                graph_patterns_or_triples_blocks=[
                    lucene_query_tb,
                    GraphPatternNotTriples(content=self._build_is_iri_filter(sr_uri)),
                ]
            )
        )
        self._lucene_query_tb = lucene_query_tb
        return GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(group_graph_patterns=[inner_ggp])
        )

    @property
    def valid_lucene_query_triple(self) -> str:
        lucene_args = [
            _sparql_string_literal(self._lucene_index_name),
            _sparql_string_literal(self._term),
        ]
        compact_filter_json = self._compact_filter_json()
        if compact_filter_json is not None:
            lucene_args.append(_sparql_string_literal(compact_filter_json))
        lucene_args.append(str(self._lucene_limit))
        return (
            f"(?focus_node ?weight ?match ?totalHits ?g ?pred) <{LUCENE.query}> "
            f"({' '.join(lucene_args)}) ."
        )

    def normalize_query_string(self, query: str) -> str:
        return query.replace(
            self._lucene_query_tb.to_string(),
            self.valid_lucene_query_triple,
        )

    @property
    def tss_list(self):
        return self._tss_list

    @property
    def inner_select_vars(self):
        return self._inner_select_vars

    @property
    def inner_select_gpnt(self):
        return self._inner_select_gpnt

    @property
    def order_by_val(self):
        return Var(value="weight")

    @property
    def order_by_direction(self):
        return "DESC"

    @property
    def limit(self):
        return self._limit

    @property
    def offset(self):
        return self._offset
