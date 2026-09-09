from typing import List, Optional

from rdflib import RDF
from sparql_grammar import (
    IRI,
    Aggregate,
    Bind,
    BuiltInCall,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    Filter,
    GroupClause,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    InlineData,
    InlineDataOneVar,
    LimitOffsetClauses,
    OrderClause,
    OrderCondition,
    RDFLiteral,
    RegexExpression,
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

from prez.config import settings
from prez.services.query_generation.grammar_helpers import construct_triples
from prez.reference_data.prez_ns import PREZ


def hash_id_expression(*terms: Var, prefix: str = "urn:hash:") -> Expression:
    """URI(CONCAT("<prefix>", SHA256(CONCAT(STR(?a), STR(?b), ...))))

    A stable IRI for a row of results, from the values that identify it.
    """
    return Expression.from_primary_expression(
        BuiltInCall.create(
            "URI",
            BuiltInCall.create(
                "CONCAT",
                RDFLiteral(value=prefix),
                BuiltInCall.create(
                    "SHA256",
                    BuiltInCall.create(
                        "CONCAT", *[BuiltInCall.create("STR", term) for term in terms]
                    ),
                ),
            ),
        )
    )


class SearchQueryRegex(ConstructQuery):
    def __init__(
        self,
        term: str,
        limit: int,
        offset: int,
        predicates: Optional[List[str]] = None,
    ):

        limit += 1  # increase the limit by one so we know if there are further pages of results.
        self._limit = limit
        self._offset = offset

        if not predicates:
            predicates = settings.search_predicates

        sr_uri: Var = Var(value="focus_node")
        pred: Var = Var(value="pred")
        match: Var = Var(value="match")
        weight: Var = Var(value="weight")
        hashid: Var = Var(value="hashID")

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

        # construct template
        ct = ConstructTemplate(construct_triples(construct_tss_list))

        # SELECT ?focus_node ?predicate ?match (SUM(?w) AS ?weight)
        # WHERE { VALUES ?pred { ... } { ... } UNION { ... } UNION { ... } }
        # GROUP BY ?focus_node ?pred ?match
        weighted_matches = SubSelect(
            select_clause=SelectClause(
                [
                    sr_uri,
                    pred,
                    match,
                    (
                        Expression.from_primary_expression(
                            Aggregate.create("SUM", Var(value="w"))
                        ),
                        weight,
                    ),
                ]
            ),
            where_clause=WhereClause(
                GroupGraphPattern(
                    GroupGraphPatternSub(
                        [
                            InlineData(
                                InlineDataOneVar(
                                    pred, [IRI(value=p) for p in predicates]
                                )
                            ),
                            GroupOrUnionGraphPattern(
                                [
                                    self.create_inner_ggp(
                                        **var_dict,
                                        sr_uri=sr_uri,
                                        pred=pred,
                                        match=match,
                                        term=term,
                                    )
                                    for var_dict in self.inner_select_args.values()
                                ]
                            ),
                        ]
                    )
                )
            ),
            solution_modifier=SolutionModifier(
                group_by=GroupClause.create(sr_uri, pred, match)
            ),
        )

        # SELECT ?focus_node ?predicate ?match ?weight (URI(CONCAT("urn:hash:",
        #   SHA256(CONCAT(STR(?focus_node), STR(?predicate), STR(?match), STR(?weight))))) AS ?hashID)
        wc = WhereClause(
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
                    where_clause=WhereClause(GroupGraphPattern(weighted_matches)),
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
            construct_template=ct,
            where_clause=wc,
            solution_modifier=SolutionModifier(),
        )

    @property
    def inner_select_args(self):
        return {
            "one": {
                "weight_val": 100,
                "function": "LCASE",
                "prefix": "",
                "case_insensitive": None,
            },
            "two": {
                "weight_val": 20,
                "function": "REGEX",
                "prefix": "^",
                "case_insensitive": True,
            },
            "three": {
                "weight_val": 10,
                "function": "REGEX",
                "prefix": "",
                "case_insensitive": True,
            },
        }

    def create_inner_ggp(
        self,
        weight_val: int,
        function: str,
        prefix: str,
        case_insensitive: Optional[bool],
        sr_uri: Var,
        pred: Var,
        match: Var,
        term: str,
    ) -> GroupGraphPattern:
        ggp = GroupGraphPattern(
            GroupGraphPatternSub(
                [
                    TriplesBlock(
                        [TriplesSameSubjectPath.from_spo(sr_uri, pred, match)]
                    ),
                    Bind(
                        Expression.from_primary_expression(numeric_literal(weight_val)),
                        Var(value="w"),
                    ),
                ]
            )
        )
        search_term = RDFLiteral(value=prefix + term)

        filter_expr = None
        if function == "REGEX":
            # FILTER REGEX(?match, "^term", "i")
            filter_expr = Filter(
                RegexExpression(
                    Expression.from_primary_expression(match),
                    Expression.from_primary_expression(search_term),
                    (
                        Expression.from_primary_expression(RDFLiteral(value="i"))
                        if case_insensitive
                        else None
                    ),
                )
            )
        elif function == "LCASE":
            # FILTER(LCASE(?match) = "search term")
            filter_expr = Filter(
                Expression.compare(BuiltInCall.create("LCASE", match), "=", search_term)
            )
        ggp.content.add_pattern(filter_expr)
        return ggp

    @property
    def tss_list(self):
        return list(self.construct_template.construct_triples.triples)

    # convenience properties for the construct query
    @property
    def construct_triples(self):
        return self.construct_template.construct_triples

    @property
    def _outer_subselect(self) -> SubSelect:
        return self.where_clause.group_graph_pattern.content

    @property
    def inner_select_vars(self):
        return self._outer_subselect.select_clause.variables

    @property
    def inner_select_gpnt(self):
        return GroupOrUnionGraphPattern(
            [self._outer_subselect.where_clause.group_graph_pattern]
        )

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
