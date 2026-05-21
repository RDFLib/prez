import json

from rdflib import RDF, Namespace
from sparql_grammar_pydantic import (
    IRI,
    AdditiveExpression,
    BrackettedExpression,
    BlankNodePropertyList,
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
    GraphNode,
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
    Object,
    ObjectList,
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
    PropertyListNotEmpty,
    RDFLiteral,
    RelationalExpression,
    SG_Path,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesNode,
    TriplesNodePath,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    UnaryExpression,
    ValueLogical,
    Var,
    VarOrIri,
    VarOrTerm,
    Verb,
    VerbPath,
    WhereClause,
)
from sparql_grammar_pydantic.grammar import PropertyList

from prez.reference_data.prez_ns import PREZ


LUCENE = Namespace("urn:jena:lucene:index#")
DEFAULT_FIELD_SPEC = "default"
EMPTY_STRING_SENTINEL = ""


def _sparql_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _compact_json(value: dict | list | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _compact_field_spec(value: str | list[str]) -> str:
    if isinstance(value, str):
        return value
    return _compact_json(value)


def _normalize_sort_direction(value: str | object | None) -> str:
    if value is None:
        return "asc"
    normalized = getattr(value, "value", value)
    if not isinstance(normalized, str):
        raise TypeError("Lucene sort direction must be a string or enum with a string value")
    return normalized.lower()


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
        search_fields: str | list[str] = DEFAULT_FIELD_SPEC,
        lucene_hit_limit: int | None = None,
        filter_json: dict | None = None,
        facets: list[str] | None = None,
        order_by: str | None = None,
        order_by_direction: str | None = None,
        include_matches: bool = True,
        pagination_pushed_down: bool = False,
    ):
        self._limit = limit
        lucene_base_limit = lucene_hit_limit if lucene_hit_limit is not None else limit
        self._pagination_pushed_down = pagination_pushed_down
        self._offset = offset
        self._lucene_limit = limit if pagination_pushed_down else lucene_base_limit
        self._lucene_offset = offset if pagination_pushed_down else 0
        self._lucene_index_name = lucene_index_name
        self._search_fields = search_fields
        self._term = "*" if term is None else term
        self._include_matches = include_matches
        self._filter_json = filter_json
        self._facets = facets or []
        self._sort_json = (
            _compact_json(
                {"field": order_by, "order": _normalize_sort_direction(order_by_direction)}
            )
            if isinstance(order_by, str) and order_by
            else None
        )
        self._facet_limit = limit
        self._lucene_facet_tb = None
        self._lucene_match_tb = None

        sr_uri = Var(value="focus_node")
        weight = Var(value="weight")
        total_hits = Var(value="totalHits")
        pred = Var(value="pred")
        match = Var(value="match")
        search_result = Var(value="searchResult")
        search_match = Var(value="searchMatch")

        self._tss_list = [
            TriplesSameSubject.from_spo(
                subject=search_result,
                predicate=IRI(value=RDF.type),
                object=IRI(value=PREZ.SearchResult),
            ),
            TriplesSameSubject.from_spo(
                subject=search_result,
                predicate=IRI(value=PREZ.searchResultURI),
                object=sr_uri,
            ),
            TriplesSameSubject.from_spo(
                subject=search_result,
                predicate=IRI(value=PREZ.searchResultWeight),
                object=weight,
            ),
        ]
        if self._include_matches:
            self._tss_list.extend(
                [
                    TriplesSameSubject.from_spo(
                        subject=search_result,
                        predicate=IRI(value=PREZ.hasSearchMatch),
                        object=search_match,
                    ),
                    TriplesSameSubject.from_spo(
                        subject=search_match,
                        predicate=IRI(value=RDF.type),
                        object=IRI(value=PREZ.SearchResultMatch),
                    ),
                    TriplesSameSubject.from_spo(
                        subject=search_match,
                        predicate=IRI(value=PREZ.searchResultPredicate),
                        object=pred,
                    ),
                    TriplesSameSubject.from_spo(
                        subject=search_match,
                        predicate=IRI(value=PREZ.searchResultMatch),
                        object=match,
                    ),
                ]
            )
        self._tss_list.append(
            TriplesSameSubject.from_spo(
                subject=IRI(value=PREZ.SearchResult),
                predicate=IRI(value=PREZ["count"]),
                object=total_hits,
            )
        )
        facet_props_vals = [
            (IRI(value=PREZ.facetName), Var(value="facetName")),
            (IRI(value=PREZ.facetValue), Var(value="facetValue")),
            (IRI(value=PREZ.facetCount), Var(value="facetCount")),
        ]
        facet_vol_list = []
        for prop, value in facet_props_vals:
            facet_vol_list.append(
                (
                    Verb(varoriri=VarOrIri(varoriri=prop)),
                    ObjectList(
                        list_object=[
                            Object(
                                graphnode=GraphNode(
                                    varorterm_or_triplesnode=VarOrTerm(varorterm=value)
                                )
                            )
                        ]
                    ),
                )
            )

        self._facet_tss_list = [
            TriplesSameSubject(
                content=(
                    TriplesNode(
                        coll_or_bnpl=BlankNodePropertyList(
                            plne=PropertyListNotEmpty(
                                verb_objectlist=facet_vol_list
                            )
                        )
                    ),
                    PropertyList(),
                )
            )
        ]
        self._inner_select_vars = [
            sr_uri,
            weight,
            total_hits,
            (self._create_hitid_expression(sr_uri, weight), search_result),
        ]
        if self._include_matches:
            self._inner_select_vars.extend(
                [
                    pred,
                    match,
                    (
                        self._create_matchid_expression(sr_uri, pred, match, weight),
                        search_match,
                    ),
                ]
            )
        self._inner_select_gpnt = self._build_inner_select_gpnt(
            sr_uri=sr_uri,
            weight=weight,
            total_hits=total_hits,
            pred=pred,
            match=match,
        )

    def _compact_filter_json(self) -> str | None:
        return _compact_json(self._filter_json)

    def _query_filter_arg(self) -> str:
        return self._compact_filter_json() or EMPTY_STRING_SENTINEL

    def _sort_json_arg(self) -> str:
        return self._sort_json or EMPTY_STRING_SENTINEL

    def _lucene_args_strings(self) -> list[str]:
        return [
            _sparql_string_literal(self._lucene_index_name),
            _sparql_string_literal(_compact_field_spec(self._search_fields)),
            _sparql_string_literal(self._term),
            _sparql_string_literal(self._query_filter_arg()),
            _sparql_string_literal(self._sort_json_arg()),
            str(self._lucene_limit),
            str(self._lucene_offset),
        ]

    def _facet_args_strings(self) -> list[str]:
        return [
            _sparql_string_literal(self._lucene_index_name),
            _sparql_string_literal(DEFAULT_FIELD_SPEC),
            _sparql_string_literal(self._term),
            _sparql_string_literal(_compact_json(self._facets)),
            _sparql_string_literal(self._query_filter_arg()),
            str(self._facet_limit),
            "0",
        ]

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

    def _create_hitid_expression(
        self,
        sr_uri: Var,
        weight: Var,
    ) -> Expression:
        return self._create_uri_hash_expression(
            "urn:hash:",
            sr_uri,
            weight,
        )

    def _create_matchid_expression(
        self,
        sr_uri: Var,
        pred: Var,
        match: Var,
        weight: Var,
    ) -> Expression:
        return self._create_uri_hash_expression(
            "urn:match:",
            sr_uri,
            pred,
            match,
            weight,
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

    @staticmethod
    def _create_predicate_path(predicate: IRI) -> SG_Path:
        return SG_Path(
            path_alternative=PathAlternative(
                sequence_paths=[
                    PathSequence(
                        list_path_elt_or_inverse=[
                            PathEltOrInverse(
                                path_elt=PathElt(
                                    path_primary=PathPrimary(value=predicate)
                                )
                            )
                        ]
                    )
                ]
            )
        )

    @staticmethod
    def _create_collection_path(*nodes: GraphNodePath) -> TriplesNodePath:
        return TriplesNodePath(
            coll_path_or_bnpl_path=CollectionPath(graphnodepath_list=list(nodes))
        )

    @staticmethod
    def _create_rdf_literal_node(value: str) -> GraphNodePath:
        return GraphNodePath(
            varorterm_or_triplesnodepath=VarOrTerm(
                varorterm=GraphTerm(content=RDFLiteral(value=value))
            )
        )

    @staticmethod
    def _create_numeric_node(value: int) -> GraphNodePath:
        return GraphNodePath(
            varorterm_or_triplesnodepath=VarOrTerm(
                varorterm=GraphTerm(content=NumericLiteral(value=value))
            )
        )

    def _build_inner_select_gpnt(
        self,
        sr_uri: Var,
        weight: Var,
        total_hits: Var,
        pred: Var,
        match: Var,
    ) -> GraphPatternNotTriples:
        hit = Var(value="hit")
        snippet = Var(value="snippet")
        lucene_query_args = self._create_collection_path(
            self._create_rdf_literal_node(self._lucene_index_name),
            self._create_rdf_literal_node(_compact_field_spec(self._search_fields)),
            self._create_rdf_literal_node(self._term),
            self._create_rdf_literal_node(self._query_filter_arg()),
            self._create_rdf_literal_node(self._sort_json_arg()),
            self._create_numeric_node(self._lucene_limit),
            self._create_numeric_node(self._lucene_offset),
        )
        lucene_query_tb = TriplesBlock(
            triples=TriplesSameSubjectPath(
                content=(
                    self._create_collection_path(
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=hit)
                        ),
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=sr_uri)
                        ),
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=weight)
                        ),
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=total_hits)
                        ),
                    ),
                    PropertyListPath(
                        plpne=PropertyListPathNotEmpty(
                            first_pair=(
                                VerbPath(path=self._create_predicate_path(IRI(value=LUCENE.query))),
                                ObjectListPath(
                                    object_paths=[
                                        ObjectPath(
                                            graph_node_path=GraphNodePath(
                                                varorterm_or_triplesnodepath=lucene_query_args
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

        lucene_match_tb = None
        if self._include_matches:
            lucene_match_tb = TriplesBlock(
                triples=TriplesSameSubjectPath(
                    content=(
                        self._create_collection_path(
                            GraphNodePath(
                                varorterm_or_triplesnodepath=VarOrTerm(varorterm=hit)
                            ),
                            GraphNodePath(
                                varorterm_or_triplesnodepath=VarOrTerm(varorterm=pred)
                            ),
                            GraphNodePath(
                                varorterm_or_triplesnodepath=VarOrTerm(varorterm=match)
                            ),
                            GraphNodePath(
                                varorterm_or_triplesnodepath=VarOrTerm(varorterm=snippet)
                            ),
                        ),
                        PropertyListPath(
                            plpne=PropertyListPathNotEmpty(
                                first_pair=(
                                    VerbPath(path=self._create_predicate_path(IRI(value=LUCENE.match))),
                                    ObjectListPath(
                                        object_paths=[
                                            ObjectPath(
                                                graph_node_path=GraphNodePath(
                                                    varorterm_or_triplesnodepath=self._create_collection_path()
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

        graph_patterns_or_triples_blocks = [lucene_query_tb]
        if lucene_match_tb is not None:
            graph_patterns_or_triples_blocks.append(lucene_match_tb)
        graph_patterns_or_triples_blocks.append(
            GraphPatternNotTriples(content=self._build_is_iri_filter(sr_uri))
        )

        inner_ggp = GroupGraphPattern(
            content=GroupGraphPatternSub(
                graph_patterns_or_triples_blocks=graph_patterns_or_triples_blocks
            )
        )
        self._lucene_query_tb = lucene_query_tb
        self._lucene_match_tb = lucene_match_tb
        return GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(group_graph_patterns=[inner_ggp])
        )

    def _build_lucene_facet_tb(
        self,
        facet_name: Var,
        facet_value: Var,
        facet_count: Var,
    ) -> TriplesBlock:
        facet_low = Var(value="facetLow")
        facet_high = Var(value="facetHigh")
        facet_args = self._create_collection_path(
            self._create_rdf_literal_node(self._lucene_index_name),
            self._create_rdf_literal_node(DEFAULT_FIELD_SPEC),
            self._create_rdf_literal_node(self._term),
            self._create_rdf_literal_node(_compact_json(self._facets)),
            self._create_rdf_literal_node(self._query_filter_arg()),
            self._create_numeric_node(self._facet_limit),
            self._create_numeric_node(0),
        )
        return TriplesBlock(
            triples=TriplesSameSubjectPath(
                content=(
                    self._create_collection_path(
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=facet_name)
                        ),
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=facet_value)
                        ),
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=facet_low)
                        ),
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=facet_high)
                        ),
                        GraphNodePath(
                            varorterm_or_triplesnodepath=VarOrTerm(varorterm=facet_count)
                        ),
                    ),
                    PropertyListPath(
                        plpne=PropertyListPathNotEmpty(
                            first_pair=(
                                VerbPath(path=self._create_predicate_path(IRI(value=LUCENE.facet))),
                                ObjectListPath(
                                    object_paths=[
                                        ObjectPath(
                                            graph_node_path=GraphNodePath(
                                                varorterm_or_triplesnodepath=facet_args
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
        graph_patterns_or_triples_blocks = [self._lucene_query_tb]
        if self._lucene_match_tb is not None:
            graph_patterns_or_triples_blocks.append(self._lucene_match_tb)
        graph_patterns_or_triples_blocks.append(
            GraphPatternNotTriples(
                content=self._build_is_iri_filter(Var(value="focus_node"))
            )
        )
        limit_offset = None
        if not self._pagination_pushed_down:
            limit_offset = LimitOffsetClauses(
                limit_clause=LimitClause(limit=self._limit),
                offset_clause=OffsetClause(offset=self._offset),
            )
        return SubSelect(
            select_clause=SelectClause(
                distinct=True,
                variables_or_all=self._inner_select_vars,
            ),
            where_clause=WhereClause(
                group_graph_pattern=GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        graph_patterns_or_triples_blocks=graph_patterns_or_triples_blocks
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
                limit_offset=limit_offset,
            ),
        )

    def _build_facet_subselect(self) -> SubSelect:
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
        return (
            f"(?hit ?focus_node ?weight ?totalHits) <{LUCENE.query}> "
            f"({' '.join(self._lucene_args_strings())}) ."
        )

    @property
    def valid_lucene_match_triple(self) -> str:
        return f"(?hit ?pred ?match ?snippet) <{LUCENE.match}> () ."

    @property
    def valid_lucene_facet_triple(self) -> str:
        return (
            f"(?facetName ?facetValue ?facetLow ?facetHigh ?facetCount) <{LUCENE.facet}> "
            f"({' '.join(self._facet_args_strings())}) ."
        )

    def normalize_query_string(self, query: str) -> str:
        normalized_query = query.replace(
            self._lucene_query_tb.to_string(),
            self.valid_lucene_query_triple,
        )
        if self._lucene_match_tb is not None:
            normalized_query = normalized_query.replace(
                self._lucene_match_tb.to_string(),
                self.valid_lucene_match_triple,
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
    def pagination_pushed_down(self) -> bool:
        return self._pagination_pushed_down

    def set_facets(self, facets: list) -> None:
        """Set facets after construction (e.g. resolved from a facet profile)."""
        self._facets = facets

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
