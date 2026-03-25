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
    ConstructQuery,
    ConstructTemplate,
    Expression,
    Filter,
    GraphNodePath,
    GraphPatternNotTriples,
    GraphTerm,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    ConstructTriples,
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
    SG_Path,
    SelectClause,
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


LUCENE = Namespace("urn:jena:lucene:index#")


def _sparql_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _compact_json(value: dict | list | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class LuceneCombinedConstructQuery(ConstructQuery):
    def __init__(
        self,
        construct_tss_list: list[TriplesSameSubject],
        search_subselect: SubSelect,
        facet_subselect: SubSelect,
        profile_triples: list[TriplesSameSubjectPath] | None = None,
        profile_gpnt: list[GraphPatternNotTriples] | None = None,
    ):
        search_branch_parts = [
            GraphPatternNotTriples(
                content=GroupOrUnionGraphPattern(
                    group_graph_patterns=[GroupGraphPattern(content=search_subselect)]
                )
            )
        ]
        if profile_triples:
            # Reverse to preserve focus-first ordering after TriplesBlock nesting.
            search_branch_parts.append(
                TriplesBlock.from_tssp_list(profile_triples[::-1])
            )
        if profile_gpnt:
            search_branch_parts.extend(profile_gpnt)

        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[
                        GraphPatternNotTriples(
                            content=GroupOrUnionGraphPattern(
                                group_graph_patterns=[
                                    GroupGraphPattern(
                                        content=GroupGraphPatternSub(
                                            graph_patterns_or_triples_blocks=search_branch_parts
                                        )
                                    ),
                                    GroupGraphPattern(content=facet_subselect),
                                ]
                            )
                        )
                    ]
                )
            )
        )

        super().__init__(
            construct_template=ConstructTemplate(
                construct_triples=ConstructTriples.from_tss_list(construct_tss_list)
            ),
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )


class SearchQueryJenaLucene:
    def __init__(
        self,
        term: str | None,
        limit: int,
        offset: int,
        lucene_index_name: str,
        filter_json: dict | None = None,
        facets: list[str] | None = None,
    ):
        self._limit = limit + 1
        self._lucene_limit = self._limit + offset
        self._offset = offset
        self._lucene_index_name = lucene_index_name
        self._term = "*" if term is None else term
        self._filter_json = filter_json
        self._facets = facets or []
        self._facet_limit = limit

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
        facet_node = Var(value="facetNode")
        self._facet_tss_list = [
            TriplesSameSubject.from_spo(
                subject=facet_node,
                predicate=IRI(value=PREZ.facetName),
                object=Var(value="facetName"),
            ),
            TriplesSameSubject.from_spo(
                subject=facet_node,
                predicate=IRI(value=PREZ.facetValue),
                object=Var(value="facetValue"),
            ),
            TriplesSameSubject.from_spo(
                subject=facet_node,
                predicate=IRI(value=PREZ.facetCount),
                object=Var(value="facetCount"),
            ),
        ]
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
        self._lucene_facet_tb = None

    def _compact_filter_json(self) -> str | None:
        return _compact_json(self._filter_json)

    def _lucene_args_strings(self) -> list[str]:
        lucene_args = [
            _sparql_string_literal(self._lucene_index_name),
            _sparql_string_literal(self._term),
        ]
        compact_filter_json = self._compact_filter_json()
        if compact_filter_json is not None:
            lucene_args.append(_sparql_string_literal(compact_filter_json))
        return lucene_args

    def _facet_args_strings(self) -> list[str]:
        lucene_args = [
            _sparql_string_literal(self._lucene_index_name),
            _sparql_string_literal(self._term),
            _sparql_string_literal(_compact_json(self._facets)),
        ]
        compact_filter_json = self._compact_filter_json()
        if compact_filter_json is not None:
            lucene_args.append(_sparql_string_literal(compact_filter_json))
        lucene_args.append(str(self._facet_limit))
        return lucene_args

    def _create_uri_hash_expression(
        self,
        prefix: str,
        *values: Var,
    ) -> Expression:
        return Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall.create_with_one_expr(
                    "URI",
                    PrimaryExpression(
                        content=BuiltInCall.create_with_n_expr(
                            "CONCAT",
                            [
                                PrimaryExpression(content=RDFLiteral(value=prefix)),
                                PrimaryExpression(
                                    content=BuiltInCall.create_with_one_expr(
                                        "SHA256",
                                        PrimaryExpression(
                                            content=BuiltInCall.create_with_n_expr(
                                                "CONCAT",
                                                [
                                                    PrimaryExpression(
                                                        content=BuiltInCall.create_with_one_expr(
                                                            "STR",
                                                            PrimaryExpression(content=value),
                                                        )
                                                    )
                                                    for value in values
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

    def _create_hashid_expression(
        self,
        sr_uri: Var,
        pred: Var,
        match: Var,
        weight: Var,
    ) -> Expression:
        return self._create_uri_hash_expression(
            "urn:hash:",
            sr_uri,
            pred,
            match,
            weight,
        )

    def _create_facet_node_expression(
        self,
        facet_name: Var,
        facet_value: Var,
        facet_count: Var,
    ) -> Expression:
        return self._create_uri_hash_expression(
            "urn:facet:",
            facet_name,
            facet_value,
            facet_count,
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

    def _build_lucene_facet_tb(
        self,
        facet_name: Var,
        facet_value: Var,
        facet_count: Var,
    ) -> TriplesBlock:
        lucene_args = [
            GraphNodePath(
                varorterm_or_triplesnodepath=VarOrTerm(
                    varorterm=GraphTerm(
                        content=RDFLiteral(value=self._lucene_index_name)
                    )
                )
            ),
            GraphNodePath(
                varorterm_or_triplesnodepath=VarOrTerm(
                    varorterm=GraphTerm(content=RDFLiteral(value=self._term))
                )
            ),
            GraphNodePath(
                varorterm_or_triplesnodepath=VarOrTerm(
                    varorterm=GraphTerm(
                        content=RDFLiteral(value=_compact_json(self._facets))
                    )
                )
            ),
        ]
        if self._filter_json is not None:
            lucene_args.append(
                GraphNodePath(
                    varorterm_or_triplesnodepath=VarOrTerm(
                        varorterm=GraphTerm(
                            content=RDFLiteral(value=self._compact_filter_json())
                        )
                    )
                )
            )
        lucene_args.append(
            GraphNodePath(
                varorterm_or_triplesnodepath=VarOrTerm(
                    varorterm=GraphTerm(
                        content=NumericLiteral(value=self._facet_limit)
                    )
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
                                        varorterm=facet_name
                                    )
                                ),
                                GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=facet_value
                                    )
                                ),
                                GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=facet_count
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
                                                                        value=LUCENE.facet
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

    def _build_search_subselect(self) -> SubSelect:
        weight = Var(value="weight")
        return SubSelect(
            select_clause=SelectClause(
                distinct=True,
                variables_or_all=self._inner_select_vars,
            ),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        graph_patterns_or_triples_blocks=[
                            self._lucene_query_tb,
                            GraphPatternNotTriples(
                                content=self._build_is_iri_filter(Var(value="focus_node"))
                            ),
                        ]
                    )
                )
            ),
            solution_modifier=SolutionModifier(
                order_by=OrderClause(
                    conditions=[
                        OrderCondition(
                            constraint_or_var=weight,
                            direction=self.order_by_direction,
                        )
                    ]
                ),
                limit_offset=LimitOffsetClauses(
                    limit_clause=LimitClause(limit=self._limit),
                    offset_clause=OffsetClause(offset=self._offset),
                ),
            ),
        )

    def _build_facet_subselect(self) -> SubSelect:
        facet_node = Var(value="facetNode")
        facet_name = Var(value="facetName")
        facet_value = Var(value="facetValue")
        facet_count = Var(value="facetCount")
        self._lucene_facet_tb = self._build_lucene_facet_tb(
            facet_name=facet_name,
            facet_value=facet_value,
            facet_count=facet_count,
        )
        return SubSelect(
            select_clause=SelectClause(
                distinct=True,
                variables_or_all=[
                    facet_name,
                    facet_value,
                    facet_count,
                    (
                        self._create_facet_node_expression(
                            facet_name=facet_name,
                            facet_value=facet_value,
                            facet_count=facet_count,
                        ),
                        facet_node,
                    ),
                ],
            ),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        graph_patterns_or_triples_blocks=[self._lucene_facet_tb]
                    )
                )
            ),
        )

    @property
    def valid_lucene_query_triple(self) -> str:
        lucene_args = self._lucene_args_strings()
        lucene_args.append(str(self._lucene_limit))
        return (
            f"(?focus_node ?weight ?match ?totalHits ?g ?pred) <{LUCENE.query}> "
            f"({' '.join(lucene_args)}) ."
        )

    @property
    def valid_lucene_facet_triple(self) -> str:
        return (
            f"(?facetName ?facetValue ?facetCount) <{LUCENE.facet}> "
            f"({' '.join(self._facet_args_strings())}) ."
        )

    def normalize_query_string(self, query: str) -> str:
        normalized_query = query.replace(
            self._lucene_query_tb.to_string(),
            self.valid_lucene_query_triple,
        )
        if self._lucene_facet_tb is not None:
            normalized_query = normalized_query.replace(
                self._lucene_facet_tb.to_string(),
                self.valid_lucene_facet_triple,
            )
        return normalized_query

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

    @property
    def has_facets(self) -> bool:
        return len(self._facets) > 0

    @property
    def facet_tss_list(self):
        return self._facet_tss_list

    def build_combined_query(
        self,
        construct_tss_list: list[TriplesSameSubject],
        profile_triples,
        profile_gpnt,
    ) -> LuceneCombinedConstructQuery:
        if not self.has_facets:
            raise ValueError("Combined query requested without Lucene facets.")
        return LuceneCombinedConstructQuery(
            construct_tss_list=construct_tss_list,
            search_subselect=self._build_search_subselect(),
            facet_subselect=self._build_facet_subselect(),
            profile_triples=profile_triples,
            profile_gpnt=profile_gpnt,
        )
