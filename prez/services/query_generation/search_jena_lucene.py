import json

from rdflib import RDF, Namespace
from sparql_grammar import (
    IRI,
    Bind,
    BlankNodePropertyList,
    BuiltInCall,
    CollectionPath,
    ConstructQuery,
    ConstructTemplate,
    Expression,
    Filter,
    GraphPatternNotTriples,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitOffsetClauses,
    ObjectList,
    ObjectListPath,
    OrderClause,
    OrderCondition,
    OrderDirection,
    PathAlternative,
    PropertyListNotEmpty,
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

from prez.services.query_generation.grammar_helpers import construct_triples
from prez.services.query_generation.search_default import hash_id_expression
from prez.reference_data.prez_ns import PREZ


LUCENE = Namespace("urn:jena:lucene:index#")
DEFAULT_FIELD_SPEC = "default"
EMPTY_STRING_SENTINEL = ""


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
        raise TypeError(
            "Lucene sort direction must be a string or enum with a string value"
        )
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
            GroupOrUnionGraphPattern([GroupGraphPattern(search_subselect)])
        ]
        if profile_triples:
            # focus-node first: this list is already in emission order
            search_branch_parts.append(TriplesBlock(list(profile_triples)))
        if profile_gpnt:
            search_branch_parts.extend(profile_gpnt)

        where_clause = WhereClause(
            GroupGraphPattern(
                GroupGraphPatternSub(
                    [
                        GroupOrUnionGraphPattern(
                            [
                                GroupGraphPattern(
                                    GroupGraphPatternSub(search_branch_parts)
                                ),
                                GroupGraphPattern(facet_subselect),
                            ]
                        )
                    ]
                )
            )
        )

        super().__init__(
            construct_template=ConstructTemplate(construct_triples(construct_tss_list)),
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
                {
                    "field": order_by,
                    "order": _normalize_sort_direction(order_by_direction),
                }
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
                search_result,
                IRI(value=RDF.type),
                IRI(value=PREZ.SearchResult),
            ),
            TriplesSameSubject.from_spo(
                search_result,
                IRI(value=PREZ.searchResultURI),
                sr_uri,
            ),
            TriplesSameSubject.from_spo(
                search_result,
                IRI(value=PREZ.searchResultWeight),
                weight,
            ),
        ]
        if self._include_matches:
            self._tss_list.extend(
                [
                    TriplesSameSubject.from_spo(
                        search_result,
                        IRI(value=PREZ.hasSearchMatch),
                        search_match,
                    ),
                    TriplesSameSubject.from_spo(
                        search_match,
                        IRI(value=RDF.type),
                        IRI(value=PREZ.SearchResultMatch),
                    ),
                    TriplesSameSubject.from_spo(
                        search_match,
                        IRI(value=PREZ.searchResultPredicate),
                        pred,
                    ),
                    TriplesSameSubject.from_spo(
                        search_match,
                        IRI(value=PREZ.searchResultMatch),
                        match,
                    ),
                ]
            )
        self._tss_list.append(
            TriplesSameSubject.from_spo(
                IRI(value=PREZ.SearchResult),
                IRI(value=PREZ["count"]),
                total_hits,
            )
        )
        facet_props_vals = [
            (IRI(value=PREZ.facetName), Var(value="facetName")),
            (IRI(value=PREZ.facetValue), Var(value="facetValue")),
            (IRI(value=PREZ.facetCount), Var(value="facetCount")),
        ]
        # [ prez:facetName ?facetName ; prez:facetValue ?facetValue ; ... ]
        self._facet_tss_list = [
            TriplesSameSubject(
                BlankNodePropertyList(
                    PropertyListNotEmpty(
                        [
                            (prop, ObjectList.create(value))
                            for prop, value in facet_props_vals
                        ]
                    )
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

    def _create_hitid_expression(
        self,
        sr_uri: Var,
        weight: Var,
    ) -> Expression:
        return hash_id_expression(sr_uri, weight)

    def _create_matchid_expression(
        self,
        sr_uri: Var,
        pred: Var,
        match: Var,
        weight: Var,
    ) -> Expression:
        return hash_id_expression(sr_uri, pred, match, weight, prefix="urn:match:")

    def _build_is_iri_filter(self, var: Var) -> Filter:
        """FILTER(isIRI(?var))"""
        return Filter(
            Expression.from_primary_expression(BuiltInCall.create("isIRI", var))
        )

    @staticmethod
    def _lucene_triple(subjects: list, predicate, arguments: list) -> TriplesBlock:
        """``( ?a ?b ... ) <predicate> ( "arg" ... )`` - how Jena's Lucene index is called.

        Both sides are collection paths: the variables the index binds on the left,
        the index arguments on the right.
        """
        return TriplesBlock(
            [
                TriplesSameSubjectPath(
                    CollectionPath(subjects),
                    PropertyListPathNotEmpty(
                        [
                            (
                                PathAlternative.iri(predicate),
                                ObjectListPath.create(CollectionPath(arguments)),
                            )
                        ]
                    ),
                )
            ]
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
        # ( ?hit ?focus_node ?weight ?totalHits ) lucene:query ( "index" "fields" ... )
        lucene_query_tb = self._lucene_triple(
            [hit, sr_uri, weight, total_hits],
            IRI(value=LUCENE.query),
            [
                RDFLiteral(value=self._lucene_index_name),
                RDFLiteral(value=_compact_field_spec(self._search_fields)),
                RDFLiteral(value=self._term),
                RDFLiteral(value=self._query_filter_arg()),
                RDFLiteral(value=self._sort_json_arg()),
                numeric_literal(self._lucene_limit),
                numeric_literal(self._lucene_offset),
            ],
        )

        lucene_match_tb = None
        if self._include_matches:
            # ( ?hit ?pred ?match ?snippet ) lucene:match ( )
            lucene_match_tb = self._lucene_triple(
                [hit, pred, match, snippet], IRI(value=LUCENE.match), []
            )

        patterns = [lucene_query_tb]
        if lucene_match_tb is not None:
            patterns.append(lucene_match_tb)
        patterns.append(self._build_is_iri_filter(sr_uri))

        inner_ggp = GroupGraphPattern(GroupGraphPatternSub(patterns))
        self._lucene_query_tb = lucene_query_tb
        self._lucene_match_tb = lucene_match_tb
        return GroupOrUnionGraphPattern([inner_ggp])

    def _build_lucene_facet_tb(
        self,
        facet_name: Var,
        facet_value: Var,
        facet_count: Var,
    ) -> TriplesBlock:
        facet_low = Var(value="facetLow")
        facet_high = Var(value="facetHigh")
        # ( ?facetName ?facetValue ?facetLow ?facetHigh ?facetCount ) lucene:facet ( ... )
        return self._lucene_triple(
            [facet_name, facet_value, facet_low, facet_high, facet_count],
            IRI(value=LUCENE.facet),
            [
                RDFLiteral(value=self._lucene_index_name),
                RDFLiteral(value=DEFAULT_FIELD_SPEC),
                RDFLiteral(value=self._term),
                RDFLiteral(value=_compact_json(self._facets)),
                RDFLiteral(value=self._query_filter_arg()),
                numeric_literal(self._facet_limit),
                numeric_literal(0),
            ],
        )

    def _build_search_subselect(self) -> SubSelect:
        weight = Var(value="weight")
        patterns = [self._lucene_query_tb]
        if self._lucene_match_tb is not None:
            patterns.append(self._lucene_match_tb)
        patterns.append(self._build_is_iri_filter(Var(value="focus_node")))
        limit_offset = None
        if not self._pagination_pushed_down:
            limit_offset = LimitOffsetClauses.create(
                limit=self._limit, offset=self._offset
            )
        return SubSelect(
            select_clause=SelectClause.create(*self._inner_select_vars, distinct=True),
            where_clause=WhereClause(GroupGraphPattern(GroupGraphPatternSub(patterns))),
            solution_modifier=SolutionModifier(
                order_by=OrderClause(
                    [OrderCondition(weight, OrderDirection(self.order_by_direction))]
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
            select_clause=SelectClause.create(
                facet_name, facet_value, facet_count, distinct=True
            ),
            where_clause=WhereClause(
                GroupGraphPattern(GroupGraphPatternSub([self._lucene_facet_tb]))
            ),
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
