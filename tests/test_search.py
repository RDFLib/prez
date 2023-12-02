import pytest
from rdflib import DCAT

from prez.reference_data.prez_ns import PREZ
from prez.services.query_generation.sparql_escaping import escape_for_lucene_and_sparql
from temp.grammar.grammar import *

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
    # Assuming that the classes are defined as per your previous message

    # Create the necessary variables
    # Create the necessary variables as PrimaryExpressions wrapped in STR function calls
    sr_uri = Var(value="search_result_uri")
    pred = Var(value="predicate")
    match = Var(value="match")
    weight = Var(value="weight")

    str_sr_uri = PrimaryExpression(
        content=BuiltInCall.create_with_one_expr(
            "STR", PrimaryExpression(content=sr_uri)
        )
    )
    str_pred = PrimaryExpression(
        content=BuiltInCall.create_with_one_expr("STR", PrimaryExpression(content=pred))
    )
    str_match = PrimaryExpression(
        content=BuiltInCall.create_with_one_expr(
            "STR", PrimaryExpression(content=match)
        )
    )
    str_weight = PrimaryExpression(
        content=BuiltInCall.create_with_one_expr(
            "STR", PrimaryExpression(content=weight)
        )
    )

    # Create the inner CONCAT function call with the STR-wrapped variables
    inner_concat = BuiltInCall.create_with_n_expr(
        "CONCAT", [str_sr_uri, str_pred, str_match, str_weight]
    )

    # Wrap the inner CONCAT in a PrimaryExpression for the SHA256 function call
    sha256_expr = PrimaryExpression(
        content=BuiltInCall.create_with_one_expr(
            "SHA256", PrimaryExpression(content=inner_concat)
        )
    )

    # Create the outer CONCAT function call, including the "urn:hash:" literal
    urn_literal = PrimaryExpression(content=RDFLiteral(value="urn:hash:"))
    outer_concat = BuiltInCall.create_with_n_expr("CONCAT", [urn_literal, sha256_expr])

    # Finally, create the URI function call
    uri_expr = BuiltInCall.create_with_one_expr(
        "URI", PrimaryExpression(content=outer_concat)
    )

    # Render the expression
    print("".join(part for part in uri_expr.render()))


def test_primary_expression():
    # Create a PrimaryExpression
    primary_expr = PrimaryExpression(content=Var(value="myVar"))

    # Use the convenience method to create a BuiltInCall with the PrimaryExpression
    str_function_call = BuiltInCall.create_with_one_expr("STR", primary_expr)

    # Render the BuiltInCall
    str_function_call.to_string()


def test_multiple_primary_expression():
    # Create a list of PrimaryExpressions
    primary_expressions = [
        PrimaryExpression(content=Var(value="var1")),
        PrimaryExpression(content=Var(value="var2")),
    ]

    # Use the convenience method to create a BuiltInCall with the list of PrimaryExpressions
    concat_function_call = BuiltInCall.create_with_n_expr("CONCAT", primary_expressions)

    # Render the BuiltInCall
    concat_function_call.to_string()


def test_aggregate():
    # function_name: str  # One of 'COUNT', 'SUM', 'MIN', 'MAX', 'AVG', 'SAMPLE', 'GROUP_CONCAT'
    # distinct: bool = False
    # expression: Optional[
    #     Union[str, Expression]
    # ] = None  # '*' for COUNT, else Expression
    # separator: Optional[str] = None  # Only used for GROUP_CONCAT
    """
    SUM(?w)
    """
    pr_exp = PrimaryExpression(content=(all_vars["w"]))
    exp = Expression.from_primary_expression(pr_exp)
    count_expression = Aggregate(function_name="SUM", expression=exp)
    print("".join(part for part in count_expression.render()))


def test_regex():
    # Example usage of RegexExpression
    pe1 = PrimaryExpression(content=Var(value="textVar"))
    pe2 = PrimaryExpression(content=RDFLiteral(value="^regexPattern"))
    pe3 = PrimaryExpression(content=RDFLiteral(value="i"))
    regex_expression = RegexExpression(
        text_expression=Expression.from_primary_expression(pe1),  # Expression for the text
        pattern_expression=Expression.from_primary_expression(
            pe2
        ),  # Expression for the regex pattern
        flags_expression=Expression.from_primary_expression(
            pe3
        ),  # Optional: Expression for regex flags
    )

    # Render the RegexExpression
    print("".join(part for part in regex_expression.render()))


def test_first_part_search():
    # Variables for outer SELECT

    expressions = [PrimaryExpression(content=v) for v in all_vars.values()]
    str_builtins = [BuiltInCall.create_with_one_expr("STR", e) for e in expressions]
    str_expressions = [PrimaryExpression(content=b) for b in str_builtins]
    urn_literal = PrimaryExpression(content=RDFLiteral(value="urn:hash:"))
    all_expressions = [urn_literal] + str_expressions
    uri_expr = BuiltInCall.create_with_n_expr("CONCAT", all_expressions)
    print("".join(part for part in uri_expr.render()))


def test_inner_ggp_search():
    # inner where
    # {
    # ?search_result_uri ?predicate ?match.
    # BIND(100 AS ?w)
    # FILTER(LCASE(?match) = "$term")
    # }
    ggp = GroupGraphPattern(content=GroupGraphPatternSub())

    # select
    # ggp.content.add_triple(
    #     TriplesSameSubjectPath.from_spo(
    #         subject=all_vars["sr_uri"],
    #         predicate=all_vars["pred"],
    #         object=all_vars["match"],
    #     )
    # )

    # bind
    bind_for_w = Bind(
        expression=Expression.from_primary_expression(
            PrimaryExpression(content=NumericLiteral(value="100"))
        ),
        var=Var(value="w"),
    )
    bind_gpnt = GraphPatternNotTriples(content=bind_for_w)
    ggp.content.add_pattern(bind_gpnt)

    # filter
    bifc = BuiltInCall(function_name="LCASE", arguments=[all_vars["match"]])
    pe_focus = PrimaryExpression(content=bifc)
    pe_st = PrimaryExpression(content=all_vars["search_term"])
    filter_expr = Filter.filter_relational(
        focus=pe_focus, comparators=pe_st, operator="="
    )
    filter_gpnt = GraphPatternNotTriples(content=filter_expr)
    ggp.content.add_pattern(filter_gpnt)

    print("".join(part for part in ggp.render()))


def test_count_query():
    subquery = """SELECT ?focus_node { ?focus_node a dcat:Dataset }"""

    klass = IRI(value=DCAT.Dataset)
    # Assuming `klass` is an instance of IRI class and `PREZ` is a predefined IRI
    count_iri = IRI(value=PREZ["count"])  # Replace with actual IRI
    count_var = Var(value="count")

    construct_triples = ConstructTriples.from_tss_list(
        [TriplesSameSubject.from_spo(subject=klass, predicate=count_iri, object=count_var)]
    )
    construct_template = ConstructTemplate(construct_triples=construct_triples)
    # Assuming `subquery` is a string containing the subquery
    subquery_str = SubSelectString(select_string=subquery)
    ggp = GroupGraphPattern(content=subquery_str)
    where_clause = WhereClause(group_graph_pattern=ggp)
    construct_query = ConstructQuery(
        construct_template=construct_template,
        where_clause=where_clause,
        solution_modifier=SolutionModifier(),  # Assuming no specific modifiers
    )


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
        (r'\\', r'\\\\\\'),
        ("/", r"\\/"),
        ("simpleTerm", "simpleTerm"),
        ('"quotedTerm"', r'\\"quotedTerm\\"'),
        ("url%20encoded%20term", "url%20encoded%20term"),
        ("term/with/slashes", r"term\\/with\\/slashes"),
        ("term-with-dashes", r"term\\-with\\-dashes"),
        ("term_with_underscores", "term_with_underscores"),
        ("term.with.periods", "term.with.periods"),
        ("term+with+pluses", r"term\\+with\\+pluses"),
        ("term%2Bwith%2Burl%2Bencoded%2Bpluses", "term%2Bwith%2Burl%2Bencoded%2Bpluses"),
    ]
)
def test_escaping(original_term, expected_result):
    # Example usage of EscapedString
    escaped_term = escape_for_lucene_and_sparql(original_term)
    assert escaped_term == expected_result


if __name__ == "__main__":
    pass
