import pytest
from rdflib import DCAT
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
    GroupGraphPattern,
    GroupGraphPatternSub,
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

from prez.reference_data.prez_ns import PREZ
from prez.services.query_generation.search_default import hash_id_expression
from prez.services.query_generation.sparql_escaping import escape_for_lucene_and_sparql

"""
SELECT ?search_result_uri ?predicate ?match ?weight (URI(CONCAT("urn:hash:", SHA256(CONCAT(STR(?search_result_uri), STR(?predicate), STR(?match), STR(?weight))))) AS ?hashID)
    WHERE {
        SELECT ?search_result_uri ?predicate ?match (SUM(?w) AS ?weight)
        WHERE
        {
          ?search_result_uri ?predicate ?match .
            VALUES ?predicate { $predicates }
            {
                ?search_result_uri ?predicate ?match .
                BIND (100 AS ?w)
                FILTER (LCASE(?match) = "$term")
            }
          UNION
            {
                ?search_result_uri ?predicate ?match .
                BIND (20 AS ?w)
                FILTER (REGEX(?match, "^$term", "i"))
            }
          UNION
            {
                ?search_result_uri ?predicate ?match .
                BIND (10 AS ?w)
                FILTER (REGEX(?match, "$term", "i"))
            }
        }
        GROUP BY ?search_result_uri ?predicate ?match
    }
        ORDER BY DESC(?weight)
"""

all_vars = {
    "sr_uri": Var(value="search_result_uri"),
    "pred": Var(value="predicate"),
    "match": Var(value="match"),
    "weight": Var(value="weight"),
    "w": Var(value="w"),
    "search_term": Var(value="search_term"),
}


def test_main():
    """The hash ID expression used to give each search result a stable IRI."""
    uri_expr = hash_id_expression(
        all_vars["sr_uri"], all_vars["pred"], all_vars["match"], all_vars["weight"]
    )
    assert uri_expr.to_string() == (
        'URI(CONCAT("urn:hash:", SHA256(CONCAT(STR(?search_result_uri), '
        "STR(?predicate), STR(?match), STR(?weight)))))"
    )


def test_primary_expression():
    # a BuiltInCall lifts a bare term into an expression argument
    str_function_call = BuiltInCall.create("STR", Var(value="myVar"))
    assert str_function_call.to_string() == "STR(?myVar)"


def test_multiple_primary_expression():
    concat_function_call = BuiltInCall.create(
        "CONCAT", Var(value="var1"), Var(value="var2")
    )
    assert concat_function_call.to_string() == "CONCAT(?var1, ?var2)"


def test_aggregate():
    """
    SUM(?w)
    """
    count_expression = Aggregate.create("SUM", all_vars["w"])
    assert count_expression.to_string() == "SUM(?w)"


def test_regex():
    regex_expression = RegexExpression(
        Expression.from_primary_expression(Var(value="textVar")),
        Expression.from_primary_expression(RDFLiteral(value="^regexPattern")),
        Expression.from_primary_expression(RDFLiteral(value="i")),
    )
    assert regex_expression.to_string() == 'REGEX(?textVar, "^regexPattern", "i")'


def test_first_part_search():
    # CONCAT("urn:hash:", STR(?a), STR(?b), ...)
    str_builtins = [BuiltInCall.create("STR", v) for v in all_vars.values()]
    uri_expr = BuiltInCall.create(
        "CONCAT", RDFLiteral(value="urn:hash:"), *str_builtins
    )
    rendered = uri_expr.to_string()
    assert rendered.startswith('CONCAT("urn:hash:", STR(?search_result_uri), ')
    assert rendered.endswith("STR(?search_term))")


def test_inner_ggp_search():
    # inner where
    # {
    # ?search_result_uri ?predicate ?match.
    # BIND(100 AS ?w)
    # FILTER(LCASE(?match) = "$term")
    # }
    ggp = GroupGraphPattern(GroupGraphPatternSub())

    ggp.content.add_triple(
        TriplesSameSubjectPath.from_spo(
            all_vars["sr_uri"], all_vars["pred"], all_vars["match"]
        )
    )

    # bind
    bind_for_w = Bind(
        Expression.from_primary_expression(numeric_literal(100)), Var(value="w")
    )
    ggp.content.add_pattern(bind_for_w)

    # filter
    filter_expr = Filter(
        Expression.compare(
            BuiltInCall.create("LCASE", all_vars["match"]), "=", all_vars["search_term"]
        )
    )
    ggp.content.add_pattern(filter_expr)

    rendered = ggp.to_string()
    assert "?search_result_uri ?predicate ?match" in rendered
    assert "BIND(100 AS ?w)" in rendered
    assert "FILTER (LCASE(?match) = ?search_term)" in rendered


def test_count_query():
    # SELECT ?focus_node { ?focus_node a dcat:Dataset }
    klass = IRI(value=DCAT.Dataset)
    focus_node = Var(value="focus_node")
    subquery = SubSelect(
        select_clause=SelectClause([focus_node]),
        where_clause=WhereClause(
            GroupGraphPattern(
                GroupGraphPatternSub(
                    [
                        TriplesBlock(
                            [TriplesSameSubjectPath.from_spo(focus_node, "a", klass)]
                        )
                    ]
                )
            )
        ),
    )

    count_iri = IRI(value=PREZ["count"])
    count_var = Var(value="count")

    construct_triples = ConstructTriples(
        [TriplesSameSubject.from_spo(klass, count_iri, count_var)]
    )
    construct_template = ConstructTemplate(construct_triples)
    where_clause = WhereClause(GroupGraphPattern(subquery))
    construct_query = ConstructQuery(
        construct_template=construct_template,
        where_clause=where_clause,
        solution_modifier=SolutionModifier(),  # Assuming no specific modifiers
    )
    rendered = construct_query.to_string()
    assert "SELECT ?focus_node" in rendered
    assert f"?focus_node a <{DCAT.Dataset}>" in rendered


@pytest.mark.parametrize(
    "original_term,expected_result",
    [
        ("+", r"\\+"),
        ("-", r"\\-"),
        ("!", r"\\!"),
        ("(", r"\\("),
        (")", r"\\)"),
        ("{", r"\\{"),
        ("}", r"\\}"),
        ("[", r"\\["),
        ("]", r"\\]"),
        ("^", r"\\^"),
        ('"', r'\\"'),
        ("~", r"\\~"),
        ("*", r"\\*"),
        ("?", r"\\?"),
        (":", r"\\:"),
        (r"\\", r"\\\\\\"),
        ("/", r"\\/"),
        ("simpleTerm", "simpleTerm"),
        ('"quotedTerm"', r'\\"quotedTerm\\"'),
        ("url%20encoded%20term", "url%20encoded%20term"),
        ("term/with/slashes", r"term\\/with\\/slashes"),
        ("term-with-dashes", r"term\\-with\\-dashes"),
        ("term_with_underscores", "term_with_underscores"),
        ("term.with.periods", "term.with.periods"),
        ("term+with+pluses", r"term\\+with\\+pluses"),
        (
            "term%2Bwith%2Burl%2Bencoded%2Bpluses",
            "term%2Bwith%2Burl%2Bencoded%2Bpluses",
        ),
    ],
)
def test_escaping(original_term, expected_result):
    # Example usage of EscapedString
    escaped_term = escape_for_lucene_and_sparql(original_term)
    assert escaped_term == expected_result


if __name__ == "__main__":
    pass
