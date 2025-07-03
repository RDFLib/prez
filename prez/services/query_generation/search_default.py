from typing import List, Optional

from rdflib import RDF
from sparql_grammar_pydantic import (
    IRI,
    Aggregate,
    Bind,
    BuiltInCall,
    Constraint,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    DataBlock,
    DataBlockValue,
    Expression,
    Filter,
    GraphPatternNotTriples,
    GroupClause,
    GroupCondition,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    InlineData,
    InlineDataOneVar,
    LimitClause,
    LimitOffsetClauses,
    NumericLiteral,
    OffsetClause,
    OrderClause,
    OrderCondition,
    PrimaryExpression,
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
)

from prez.config import settings
from prez.reference_data.prez_ns import PREZ


class SearchQueryRegex(ConstructQuery):
    def __init__(
        self,
        term: str,
        limit: int,
        offset: int,
        predicates: Optional[List[str]] = None,
    ):

        limit += 1  # increase the limit by one so we know if there are further pages of results.

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
            TriplesSameSubject.from_spo(subject=hashid, predicate=p, object=v)
            for p, v in ct_map.items()
        ]

        # construct template
        ct = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(construct_tss_list)
        )
        wc = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=SubSelect(
                    # SELECT ?focus_node ?predicate ?match ?weight (URI(CONCAT("urn:hash:",
                    #   SHA256(CONCAT(STR(?focus_node), STR(?predicate), STR(?match), STR(?weight))))) AS ?hashID)
                    select_clause=SelectClause(
                        variables_or_all=[
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
                            content=SubSelect(
                                # SELECT ?focus_node ?predicate ?match (SUM(?w) AS ?weight)
                                select_clause=SelectClause(
                                    variables_or_all=[
                                        sr_uri,
                                        pred,
                                        match,
                                        (
                                            Expression.from_primary_expression(
                                                PrimaryExpression(
                                                    content=BuiltInCall(
                                                        other_expressions=Aggregate(
                                                            function_name="SUM",
                                                            expression=Expression.from_primary_expression(
                                                                PrimaryExpression(
                                                                    content=Var(
                                                                        value="w"
                                                                    )
                                                                )
                                                            ),
                                                        )
                                                    )
                                                )
                                            ),
                                            weight,
                                        ),
                                    ]
                                ),
                                where_clause=WhereClause(
                                    group_graph_pattern=GroupGraphPattern(
                                        content=GroupGraphPatternSub(
                                            graph_patterns_or_triples_blocks=[
                                                GraphPatternNotTriples(
                                                    content=InlineData(
                                                        data_block=DataBlock(
                                                            block=InlineDataOneVar(
                                                                variable=pred,
                                                                datablockvalues=[
                                                                    DataBlockValue(
                                                                        value=p
                                                                    )
                                                                    for p in [
                                                                        IRI(value=p)
                                                                        for p in predicates
                                                                    ]
                                                                ],
                                                            )
                                                        )
                                                    )
                                                ),
                                                GraphPatternNotTriples(
                                                    content=GroupOrUnionGraphPattern(
                                                        group_graph_patterns=[
                                                            self.create_inner_ggp(
                                                                **var_dict,
                                                                sr_uri=sr_uri,
                                                                pred=pred,
                                                                match=match,
                                                                term=term,
                                                            )
                                                            for var_dict in self.inner_select_args.values()
                                                        ]
                                                    )
                                                ),
                                            ]
                                        )
                                    )
                                ),
                                solution_modifier=SolutionModifier(
                                    group_by=GroupClause(
                                        group_conditions=[
                                            GroupCondition(condition=sr_uri),
                                            GroupCondition(condition=pred),
                                            GroupCondition(condition=match),
                                        ]
                                    )
                                ),
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
            content=GroupGraphPatternSub(
                triples_block=TriplesBlock.from_tssp_list(
                    [
                        TriplesSameSubjectPath.from_spo(
                            subject=sr_uri,
                            predicate=pred,
                            object=match,
                        )
                    ]
                ),
                graph_patterns_or_triples_blocks=[
                    GraphPatternNotTriples(
                        content=Bind(
                            expression=Expression.from_primary_expression(
                                PrimaryExpression(
                                    content=NumericLiteral(value=weight_val)
                                )
                            ),
                            var=Var(value="w"),
                        )
                    )
                ],
            )
        )
        # FILTER (REGEX(?match, "^$term", "i"))
        pe_st = PrimaryExpression(content=RDFLiteral(value=(prefix + term)))

        filter_expr = None
        if function == "REGEX":
            filter_expr = Filter(
                constraint=Constraint(
                    content=BuiltInCall(
                        other_expressions=RegexExpression(
                            text_expression=Expression.from_primary_expression(
                                PrimaryExpression(content=match)
                            ),  # Expression for the text
                            pattern_expression=Expression.from_primary_expression(
                                pe_st
                            ),
                            flags_expression=(
                                Expression.from_primary_expression(
                                    PrimaryExpression(content=RDFLiteral(value="i"))
                                )
                                if case_insensitive
                                else None
                            ),
                        )
                    )
                )
            )

        # filter e.g. FILTER(LCASE(?match) = "search term")
        elif function == "LCASE":
            filter_expr = Filter.filter_relational(
                focus=PrimaryExpression(
                    content=BuiltInCall(function_name=function, arguments=[match])
                ),
                comparators=pe_st,
                operator="=",
            )
        ggp.content.add_pattern(GraphPatternNotTriples(content=filter_expr))
        return ggp

    @property
    def tss_list(self):
        return self.construct_template.construct_triples.to_tss_list()

    # convenience properties for the construct query
    @property
    def construct_triples(self):
        return self.construct_template.construct_triples

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
