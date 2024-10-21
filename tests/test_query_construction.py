from itertools import product

import pytest
from rdflib import RDF, RDFS, SKOS
from rdflib.namespace import GEO
from sparql_grammar_pydantic import (
    IRI,
    Var,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    SubSelect,
    SelectClause,
    WhereClause,
    GroupGraphPattern,
    GroupGraphPatternSub,
    TriplesBlock,
    SolutionModifier,
    LimitOffsetClauses,
    LimitClause,
    Expression,
    PrimaryExpression,
    BuiltInCall,
    Aggregate,
    ConditionalOrExpression,
    ConditionalAndExpression,
    ValueLogical,
    RelationalExpression,
    NumericExpression,
    AdditiveExpression,
    MultiplicativeExpression,
    UnaryExpression,
    NumericLiteral,
    RDFLiteral,
    Bind,
    GraphPatternNotTriples,
    GroupOrUnionGraphPattern,
    ConstructTemplate,
    BlankNode,
    Anon,
    ConstructTriples,
    ConstructQuery,
)

from prez.services.query_generation.classes import ClassesSelectQuery
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.prefixes import PrefixQuery
from prez.services.query_generation.search_default import (
    SearchQueryRegex,
)
from prez.services.query_generation.umbrella import PrezQueryConstructor


def test_basic_object():
    PrezQueryConstructor(
        profile_triples=[
            TriplesSameSubjectPath.from_spo(
                subject=IRI(value="https://test-object"),
                predicate=IRI(value="https://prez.dev/ont/label"),
                object=Var(value="label"),
            ),
            TriplesSameSubjectPath.from_spo(
                subject=IRI(value="https://test-object"),
                predicate=IRI(value="https://property"),
                object=Var(value="propValue"),
            ),
        ],
    )


def test_basic_listing():
    test = PrezQueryConstructor(
        profile_triples=[
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDF.type)),
                object=IRI(value=str(GEO.Feature)),
            ),
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value="https://property"),
                object=Var(value="propValue"),
            ),
        ],
        inner_select_tssp_list=[
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDF.type)),
                object=IRI(value=str(GEO.Feature)),
            ),
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDFS.label)),
                object=Var(value="label"),
            ),
        ],
        limit=10,
        offset=0,
        order_by=Var(value="label"),
        order_by_direction="ASC",
    )
    print("")


def test_search_query_regex():
    sq = SearchQueryRegex(term="test", predicates=[RDFS.label], limit=10, offset=0)
    test = PrezQueryConstructor(
        profile_triples=[
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDF.type)),
                object=IRI(value=str(GEO.Feature)),
            ),
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value="https://property"),
                object=Var(value="propValue"),
            ),
        ],
        construct_tss_list=sq.construct_triples.to_tss_list()
        + [
            TriplesSameSubject.from_spo(
                IRI(value="https://s"), IRI(value="https://p"), IRI(value="https://o")
            )
        ],
        inner_select_vars=sq.inner_select_vars,
        inner_select_gpnt=[sq.inner_select_gpnt],
        limit=sq.limit,
        offset=sq.offset,
        order_by=sq.order_by,
        order_by_direction=sq.order_by_direction,
    )
    print(test)


def test_classes():
    test = ClassesSelectQuery(
        iris=[IRI(value="https://test1"), IRI(value="https://test2")]
    )
    print(test.to_string())


def test_prefix_query():
    test = PrefixQuery()
    print(test.to_string())


values = [Var(value="var"), IRI(value="http://example.org/iri")]
combs = [p for p in product(values, repeat=3)]


@pytest.mark.parametrize("s,p,o", combs)
def test_triples_ssp(s, p, o):
    result = TriplesSameSubjectPath.from_spo(s, p, o)
    print(result)
    assert isinstance(result, TriplesSameSubjectPath)


@pytest.mark.parametrize("s,p,o", combs)
def test_triples_ss(s, p, o):
    result = TriplesSameSubject.from_spo(s, p, o)
    print(result)
    assert isinstance(result, TriplesSameSubject)


def test_concept_hierarchy_top_concepts():
    parent_uri = IRI(value="https://parent-uri")
    parent_child_predicates = (
        IRI(value=SKOS.hasTopConcept),
        IRI(value=SKOS.topConceptOf),
    )
    child_grandchild_predicates = (IRI(value=SKOS.narrower), IRI(value=SKOS.broader))

    tc_cq = ConceptHierarchyQuery(
        parent_uri=parent_uri,
        parent_child_predicates=parent_child_predicates,
        child_grandchild_predicates=child_grandchild_predicates,
    )
    tc_cq.to_string()


def test_concept_hierarchy_narrowers():
    parent_uri = IRI(value="https://concept-uri")
    parent_child_predicates = (IRI(value=SKOS.narrower), IRI(value=SKOS.broader))

    tc_cq = ConceptHierarchyQuery(
        parent_uri=parent_uri,
        parent_child_predicates=parent_child_predicates,
    )
    tc_cq.to_string()


def test_count_query():
    inner_ss = SubSelect(
        select_clause=SelectClause(variables_or_all=[Var(value="focus_node")]),
        where_clause=WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[
                        TriplesBlock.from_tssp_list(
                            [
                                TriplesSameSubjectPath.from_spo(
                                    subject=Var(value="focus_node"),
                                    predicate=IRI(value=RDF.type),
                                    object=IRI(
                                        value="http://www.w3.org/ns/sosa/Sampling"
                                    ),
                                )
                            ]
                        )
                    ]
                )
            )
        ),
        solution_modifier=SolutionModifier(
            limit_offset=LimitOffsetClauses(limit_clause=LimitClause(limit=1001)),
        ),
    )
    count_expression = Expression.from_primary_expression(
        PrimaryExpression(
            content=BuiltInCall(
                other_expressions=Aggregate(
                    function_name="COUNT",
                    distinct=True,
                    expression=Expression.from_primary_expression(
                        PrimaryExpression(content=Var(value="focus_node"))
                    ),
                )
            )
        )
    )
    outer_ss = SubSelect(
        select_clause=SelectClause(
            variables_or_all=[(count_expression, Var(value="count"))],
        ),
        where_clause=WhereClause(
            group_graph_pattern=GroupGraphPattern(content=inner_ss)
        ),
    )
    outer_ss_ggp = GroupGraphPattern(content=outer_ss)
    count_equals_1001_expr = Expression(
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
                                                    content=Var(value="count")
                                                )
                                            )
                                        )
                                    )
                                ),
                                operator="=",
                                right=NumericExpression(
                                    additive_expression=AdditiveExpression(
                                        base_expression=MultiplicativeExpression(
                                            base_expression=UnaryExpression(
                                                primary_expression=PrimaryExpression(
                                                    content=NumericLiteral(value=1001)
                                                )
                                            )
                                        )
                                    )
                                ),
                            )
                        )
                    ]
                )
            ]
        )
    )
    gt_1000_exp = Expression.from_primary_expression(
        PrimaryExpression(content=RDFLiteral(value=">1000"))
    )
    str_count_exp = Expression.from_primary_expression(
        PrimaryExpression(
            content=BuiltInCall.create_with_one_expr(
                function_name="STR",
                expression=PrimaryExpression(content=Var(value="count")),
            )
        )
    )
    bind = Bind(
        expression=Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall(
                    function_name="IF",
                    arguments=[count_equals_1001_expr, gt_1000_exp, str_count_exp],
                )
            )
        ),
        var=Var(value="count_str"),
    )
    wc = WhereClause(
        group_graph_pattern=GroupGraphPattern(
            content=GroupGraphPatternSub(
                graph_patterns_or_triples_blocks=[
                    GraphPatternNotTriples(
                        content=GroupOrUnionGraphPattern(
                            group_graph_patterns=[outer_ss_ggp]
                        )
                    ),
                    GraphPatternNotTriples(content=bind),
                ]
            )
        )
    )
    construct_template = ConstructTemplate(
        construct_triples=ConstructTriples.from_tss_list(
            [
                TriplesSameSubject.from_spo(
                    subject=BlankNode(value=Anon()),
                    predicate=IRI(value="https://prez.dev/count"),
                    object=Var(value="count_str"),
                )
            ]
        )
    )
    query = ConstructQuery(
        construct_template=construct_template,
        where_clause=wc,
        solution_modifier=SolutionModifier(),
    )
    print(query)
