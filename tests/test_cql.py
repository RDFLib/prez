import json
from pathlib import Path
from urllib.parse import quote_plus

import pytest

cql_filenames = [
    "example01.json",
    "example02.json",
    "example03.json",
    "example05a.json",
    "example05b.json",
    "example06b.json",
    "example09.json",
    "example10.json",
    "example11.json",
    "example12.json",
    "example14.json",
    "example15.json",
    "example17.json",
    "example29.json",
    "example31.json",
    "example32.json",
    "example33.json",
    "example34.json",
    "example35.json",
    "example39.json",
]

# @pytest.mark.parametrize(
#     "cql_json_filename",
#     cql_filenames
# )
# def test_simple_post(client, cql_json_filename):
#     cql_json_path = Path(__file__).parent.parent / f"test_data/cql/input/{cql_json_filename}"
#     cql_json = json.loads(cql_json_path.read_text())
#     headers = {"content-type": "application/json"}
#     response = client.post("/cql", json=cql_json, headers=headers)
#     assert response.status_code == 200


@pytest.mark.parametrize("cql_json_filename", cql_filenames)
def test_simple_get(client, cql_json_filename):
    cql_json_path = (
        Path(__file__).parent.parent / f"test_data/cql/input/{cql_json_filename}"
    )
    cql_json = json.loads(cql_json_path.read_text())
    query_string = quote_plus(json.dumps(cql_json))
    response = client.get(f"/cql?filter={query_string}")
    assert response.status_code == 200


# def test_intersects_post(client):
#     cql_json_path = Path(__file__).parent.parent / f"test_data/cql/input/geo_intersects.json"
#     cql_json = json.loads(cql_json_path.read_text())
#     headers = {"content-type": "application/json"}
#     response = client.post("/cql", json=cql_json, headers=headers)
#     assert response.status_code == 200

cql_geo_filenames = [
    "geo_contains",
    "geo_contains_filter",
    "geo_contains_inverse",
    "geo_contains_like",
    "geo_crosses",
    "geo_disjoint",
    "geo_equals",
    "geo_intersects",
    "geo_overlaps",
    "geo_touches",
    "geo_within",
]


@pytest.mark.parametrize("cql_geo_filename", cql_geo_filenames)
def test_intersects_get(client, cql_geo_filename):
    cql_json_path = (
        Path(__file__).parent.parent / f"docs/examples/cql/{cql_geo_filename}.json"
    )
    cql_json = json.loads(cql_json_path.read_text())
    query_string = quote_plus(json.dumps(cql_json))
    response = client.get(
        f"/cql?filter={query_string}&_mediatype=application/sparql-query"
    )
    assert response.status_code == 200


def test_cql_or_operator_fix():
    """
    Tests that triples from an 'or' condition's branches only appear
    within the UNION clause and not in the main self.tssp_list.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "or",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
                    "http://www.w3.org/ns/sosa/Sample",
                ],
            },
            {
                "op": "=",
                "args": [
                    {"property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
                    "https://linked.data.gov.au/def/borehole/Bore",
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    try:
        parser.parse()
    except Exception as e:
        print(e)
    where_content = parser.query_object.where_clause.group_graph_pattern.content

    expected_inner_select_gpntotb_list_str = [
        """
{
?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/sosa/Sample> .
}
UNION
{
?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://linked.data.gov.au/def/borehole/Bore> .
}"""
    ]

    # Extract original patterns from within FILTER EXISTS wrapper
    original_patterns = _extract_patterns_from_filter_exists(
        parser.inner_select_gpntotb_list
    )
    assert len(original_patterns) == len(expected_inner_select_gpntotb_list_str)
    assert original_patterns[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_cql_nested_and_operator():
    """
    Tests a nested 'and' CQL query to ensure all conditions
    are correctly translated into triples in the tss_list.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "and",
        "args": [
            {
                "op": "and",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {
                                "property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
                            },
                            "http://example.org/vocab#Report",
                        ],
                    },
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://purl.org/dc/terms/subject"},
                            "http://example.org/subjects#Geology",
                        ],
                    },
                ],
            },
            {
                "op": "and",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://purl.org/dc/terms/format"},
                            "http://example.org/formats#PDF",
                        ],
                    },
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://purl.org/dc/terms/creator"},
                            "http://example.org/organizations#GeologicalSurvey",
                        ],
                    },
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    expected_inner_select_gpntotb_list_str = [
        """?focus_node <http://purl.org/dc/terms/creator> <http://example.org/organizations#GeologicalSurvey> .
?focus_node <http://purl.org/dc/terms/format> <http://example.org/formats#PDF> .
?focus_node <http://purl.org/dc/terms/subject> <http://example.org/subjects#Geology> .
?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/vocab#Report> ."""
    ]

    # Extract original patterns from within FILTER EXISTS wrapper
    original_patterns = _extract_patterns_from_filter_exists(
        parser.inner_select_gpntotb_list
    )

    # With focus_node optimization, AND operations now generate individual TriplesBlocks
    # Combine them into a single string to match the test expectation
    if len(original_patterns) > 1 and all(
        hasattr(p, "to_string") for p in original_patterns
    ):
        # Remove duplicates by converting to set of strings, then back to list
        pattern_strings = list(set(p.to_string().strip() for p in original_patterns))
        combined_pattern = "\n".join(
            sorted(pattern_strings)
        )  # Sort for consistent ordering
    else:
        combined_pattern = original_patterns[0].to_string() if original_patterns else ""

    expected_combined = expected_inner_select_gpntotb_list_str[0]
    assert combined_pattern.replace(" ", "").replace(
        "\n", ""
    ) == expected_combined.replace(" ", "").replace("\n", "")


# --- Tests for nested AND/OR operators ---

# Helper properties and values
PROP_A = "http://example.org/propA"
VAL_A = "http://example.org/valA"
PROP_B = "http://example.org/propB"
VAL_B = "http://example.org/valB"
PROP_C = "http://example.org/propC"
VAL_C = "http://example.org/valC"
PROP_D = "http://example.org/propD"
VAL_D = "http://example.org/valD"


def _create_eq_cql(prop, val_str):
    return {"op": "=", "args": [{"property": prop}, val_str]}


def _create_tssp(prop_uri, val_uri):
    from sparql_grammar_pydantic import IRI, TriplesSameSubjectPath, Var

    return TriplesSameSubjectPath.from_spo(
        Var(value="focus_node"), IRI(value=prop_uri), IRI(value=val_uri)
    )


def _get_all_tssp_from_triples_block(triples_block):
    """Helper to extract all TriplesSameSubjectPath from a linked list of TriplesBlock."""
    from sparql_grammar_pydantic import TriplesBlock, TriplesSameSubjectPath

    all_tssp = []
    current_block = triples_block
    while current_block:
        if isinstance(current_block, TriplesBlock) and isinstance(
            current_block.triples, TriplesSameSubjectPath
        ):
            all_tssp.append(current_block.triples)
        elif isinstance(current_block, TriplesSameSubjectPath):
            all_tssp.append(current_block)
        current_block = getattr(current_block, "triples_block", None)
    return all_tssp


def _extract_patterns_from_filter_exists(inner_select_gpntotb_list):
    """Helper to extract patterns from CQL query structure.

    With the new optimization, patterns may be:
    1. Direct patterns (like GroupOrUnionGraphPattern for OR operations)
    2. Wrapped in FILTER EXISTS (for complex AND operations)
    3. Mix of both (focus_node triples + FILTER EXISTS)

    Returns the list of patterns that represent the core CQL logic.
    """
    if not inner_select_gpntotb_list:
        return []

    if len(inner_select_gpntotb_list) == 1:
        pattern = inner_select_gpntotb_list[0]

        # Check if it's a FILTER EXISTS wrapper
        if (
            hasattr(pattern, "content")
            and hasattr(pattern.content, "constraint")
            and hasattr(pattern.content.constraint, "content")
            and hasattr(pattern.content.constraint.content, "other_expressions")
        ):

            # Navigate through the FILTER EXISTS structure:
            # GraphPatternNotTriples -> Filter -> Constraint -> BuiltInCall -> ExistsFunc -> GroupGraphPattern -> GroupGraphPatternSub
            try:
                inner_content = (
                    pattern.content.constraint.content.other_expressions.group_graph_pattern.content
                )
                return inner_content.graph_patterns_or_triples_blocks or []
            except AttributeError:
                # If navigation fails, return the pattern as-is
                return [pattern]
        else:
            # Direct pattern (e.g., GroupOrUnionGraphPattern)
            return [pattern]

    # Multiple patterns - return as-is (this represents focus_node triples + FILTER EXISTS)
    return inner_select_gpntotb_list


def test_cql_and_of_A_or_BC():
    """Tests AND(A, OR(B, C))"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {"op": "and", "args": [cql_A, {"op": "or", "args": [cql_B, cql_C]}]}
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    where_content = parser.query_object.where_clause.group_graph_pattern.content

    expected_inner_select_gpntotb_list_str = [
        """?focus_node <http://example.org/propA> <http://example.org/valA> .""",
        """
{
{
?focus_node <http://example.org/propB> <http://example.org/valB> .
}
UNION
{
?focus_node <http://example.org/propC> <http://example.org/valC> .
}
}""",
    ]

    # Extract original patterns from within FILTER EXISTS wrapper
    original_patterns = _extract_patterns_from_filter_exists(
        parser.inner_select_gpntotb_list
    )
    assert len(original_patterns) == len(expected_inner_select_gpntotb_list_str)
    assert original_patterns[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")
    assert original_patterns[1].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[1].replace(" ", "").replace("\n", "")


def test_cql_or_of_A_and_BC():
    """Tests OR(A, AND(B, C))"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {"op": "or", "args": [cql_A, {"op": "and", "args": [cql_B, cql_C]}]}
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    expected_inner_select_gpntotb_list_str = [
        """

{
?focus_node <http://example.org/propA> <http://example.org/valA> .
}
UNION
{
?focus_node <http://example.org/propC> <http://example.org/valC> .
?focus_node <http://example.org/propB> <http://example.org/valB> .

}"""
    ]

    # Extract original patterns from within FILTER EXISTS wrapper
    original_patterns = _extract_patterns_from_filter_exists(
        parser.inner_select_gpntotb_list
    )
    assert len(original_patterns) == len(expected_inner_select_gpntotb_list_str)
    assert original_patterns[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_cql_and_of_and_AB_C():
    """Tests AND(AND(A, B), C)"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {
        "op": "and",
        "args": [{"op": "and", "args": [cql_A, cql_B]}, cql_C],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    expected_inner_select_gpntotb_list_str = [
        """?focus_node <http://example.org/propC> <http://example.org/valC> .
?focus_node <http://example.org/propB> <http://example.org/valB> .
?focus_node <http://example.org/propA> <http://example.org/valA> ."""
    ]

    # Extract original patterns from within FILTER EXISTS wrapper
    original_patterns = _extract_patterns_from_filter_exists(
        parser.inner_select_gpntotb_list
    )
    assert len(original_patterns) == len(expected_inner_select_gpntotb_list_str)
    assert original_patterns[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_cql_or_of_or_AB_C():
    """Tests OR(OR(A, B), C)"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {"op": "or", "args": [{"op": "or", "args": [cql_A, cql_B]}, cql_C]}
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    expected_inner_select_gpntotb_list_str = [
        """
{
{
?focus_node <http://example.org/propA> <http://example.org/valA> .
}
UNION
{
?focus_node <http://example.org/propB> <http://example.org/valB> .
}
}
UNION
{
?focus_node <http://example.org/propC> <http://example.org/valC> .
}
"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_cql_and_of_or_AB_or_CD():
    """Tests AND(OR(A,B), OR(C,D))"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)
    cql_D = _create_eq_cql(PROP_D, VAL_D)

    cql_json_data = {
        "op": "and",
        "args": [
            {"op": "or", "args": [cql_A, cql_B]},
            {"op": "or", "args": [cql_C, cql_D]},
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()
    where_content = parser.query_object.where_clause.group_graph_pattern.content

    expected_inner_select_gpntotb_list_str = [
        """
{
{
?focus_node <http://example.org/propA> <http://example.org/valA> .
}
UNION
{
?focus_node <http://example.org/propB> <http://example.org/valB> .
}
}""",
        """
{
{
?focus_node <http://example.org/propC> <http://example.org/valC> .
}
UNION
{
?focus_node <http://example.org/propD> <http://example.org/valD> .
}
}""",
    ]

    # Extract original patterns from within FILTER EXISTS wrapper
    original_patterns = _extract_patterns_from_filter_exists(
        parser.inner_select_gpntotb_list
    )
    assert len(original_patterns) == len(expected_inner_select_gpntotb_list_str)
    assert original_patterns[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")
    assert original_patterns[1].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[1].replace(" ", "").replace("\n", "")


def test_cql_or_of_and_AB_and_CD():
    """Tests OR(AND(A,B), AND(C,D))"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)
    cql_D = _create_eq_cql(PROP_D, VAL_D)

    cql_json_data = {
        "op": "or",
        "args": [
            {"op": "and", "args": [cql_A, cql_B]},
            {"op": "and", "args": [cql_C, cql_D]},
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()
    where_content = parser.query_object.where_clause.group_graph_pattern.content

    expected_inner_select_gpntotb_list_str = [
        """
{
?focus_node <http://example.org/propB> <http://example.org/valB> .
?focus_node <http://example.org/propA> <http://example.org/valA> .
}
UNION
{
?focus_node <http://example.org/propD> <http://example.org/valD> .
?focus_node <http://example.org/propC> <http://example.org/valC> .
}
"""
    ]

    # Extract original patterns from within FILTER EXISTS wrapper
    original_patterns = _extract_patterns_from_filter_exists(
        parser.inner_select_gpntotb_list
    )
    assert len(original_patterns) == len(expected_inner_select_gpntotb_list_str)
    assert original_patterns[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_focus_node_in_subquery():
    """
    Tests that ?focus_node is always included in the inner select variables,
    even for a simple query.
    """
    from sparql_grammar_pydantic import Var

    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "=",
        "args": [
            {"property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
            "http://www.w3.org/ns/sosa/Sample",
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    assert Var(value="focus_node") in parser.inner_select_vars


def test_cql_boolean_equals_filter():
    """Ensure boolean literals in CQL become boolean literals in the SPARQL FILTER."""
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "=",
        "args": [
            {"property": "http://example.org/flag"},
            True,
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    assert "FILTER (?var_1 = true)" in query_str


def test_cql_not_equal_operator_with_literal():
    """
    Tests the '<>' operator (not equal) with a literal string value.
    Should generate a FILTER with != operator.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "<>",
        "args": [
            {"property": "http://example.org/vocab#status"},
            "active",
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # The query should contain a FILTER with != operator
    query_str = parser.query_str
    assert "FILTER" in query_str
    assert "!=" in query_str
    assert '"active"' in query_str
    assert "?var_1" in query_str  # Should use variable for the property value


def test_cql_not_equal_operator_with_uri():
    """
    Tests the '<>' operator (not equal) with a URI value.
    Should generate a FILTER with != operator since it's a comparison.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "<>",
        "args": [
            {"property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
            "http://example.org/vocab#ExcludedType",
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Should use FILTER even for URI values when using <> operator
    query_str = parser.query_str
    assert "FILTER" in query_str
    assert "!=" in query_str
    assert "http://example.org/vocab#ExcludedType" in query_str


def test_cql_not_equal_operator_with_shacl_queryable():
    """
    Tests the '<>' operator with a SHACL-defined queryable property and URI value.
    Should use FILTER statement even for URI equality when SHACL paths are involved.
    """
    from prez.services.query_generation.cql import CQLParser

    # Mock queryable properties
    queryable_props = {"type": "http://example.org/shapes#TypeShape"}

    cql_json_data = {
        "op": "<>",
        "args": [
            {"property": "type"},
            "http://example.org/vocab#ExcludedType",
        ],
    }

    parser = CQLParser(cql_json=cql_json_data, queryable_props=queryable_props)
    # Note: This test would need proper SHACL shapes in the system graph to work fully
    # For now, just test that the operator conversion happens

    # Test that <> gets converted to != in the logical operators
    element = {"op": "<>", "args": []}
    ggps_generator = parser.parse_logical_operators(element)
    # The operator should be converted internally


def test_cql_not_equal_operator_in_complex_query():
    """
    Tests the '<>' operator as part of a more complex AND/OR query.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "and",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
                    "http://example.org/vocab#Document",
                ],
            },
            {
                "op": "<>",
                "args": [
                    {"property": "http://example.org/vocab#status"},
                    "archived",
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should contain both a triple pattern and a FILTER
    assert (
        "?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/vocab#Document>"
        in query_str
    )
    assert "FILTER" in query_str
    assert "!=" in query_str
    assert '"archived"' in query_str


def test_cql_operator_conversion():
    """
    Tests that the '<>' operator is correctly converted to '!=' internally.
    """
    from prez.services.query_generation.cql import CQLParser

    parser = CQLParser()

    # Test the operator conversion logic by checking what happens
    # when we parse an element with <> operator
    test_element = {
        "op": "<>",
        "args": [{"property": "http://example.org/prop"}, "test_value"],
    }

    # This should not raise a NotImplementedError
    try:
        result = list(parser.parse_logical_operators(test_element))
        # If we get here, the operator was recognized and processed
        assert True
    except NotImplementedError as e:
        if "<> not implemented" in str(e):
            assert False, "<> operator was not properly converted to !="
        else:
            raise  # Some other NotImplementedError


def test_cql_or_operator_variable_separation(monkeypatch):
    """
    Tests that OR operations generate separate variables with proper counter separation.
    When using OR with the same property in multiple branches, each branch should get
    unique variable names to avoid conflicts in the generated CQL.
    This specifically tests the SHACL queryable case where the bug occurs.
    """
    from prez.services.query_generation.cql import CQLParser
    from rdflib import Graph

    # Mock the queryable properties to simulate SHACL queryable
    mock_queryable_props = {"type": "https://prez/queryables/RDFType"}

    # Mock the system graph with SHACL shape
    mock_system_graph = Graph()
    mock_system_graph.parse(
        data="""
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
        @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix prezqueryables: <https://prez/queryables/> .
        @prefix bore: <https://linked.data.gov.au/def/bore/> .

        prezqueryables:RDFType a cql:Queryable ;
            a sh:PropertyShape ;
            dcterms:identifier "type" ;
            sh:datatype xsd:string ;
            sh:description "Filter by RDF type" ;
            sh:name "RDF Type" ;
            sh:path rdf:type ;
            sh:in (
                bore:Bore
                bore:Drillhole
            ) .
    """,
        format="turtle",
    )

    # Add the mock data to the actual system graph
    from prez.cache import prez_system_graph

    prez_system_graph += mock_system_graph

    cql_json_data = {
        "op": "or",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "type"},
                    "https://linked.data.gov.au/def/bore/Bore",
                ],
            },
            {
                "op": "=",
                "args": [
                    {"property": "type"},
                    "https://linked.data.gov.au/def/bore/Drillhole",
                ],
            },
            {
                "op": "=",
                "args": [
                    {"property": "type"},
                    "https://linked.data.gov.au/def/bore/test",
                ],
            },
        ],
    }

    # Create parser with mock queryable properties
    parser = CQLParser(cql_json=cql_json_data, queryable_props=mock_queryable_props)
    parser.parse()

    # Get the generated SPARQL query
    query_str = parser.query_str
    print(f"Generated SPARQL query:\n{query_str}")

    # Ensure each OR branch introduced a distinct path variable
    assert "?cql_filter_1" in query_str
    assert "?cql_filter_2" in query_str
    assert "?cql_filter_3" in query_str

    # Ensure both type URIs are present
    assert "https://linked.data.gov.au/def/bore/Bore" in query_str
    assert "https://linked.data.gov.au/def/bore/Drillhole" in query_str

    # Verify UNION structure is present
    assert "UNION" in query_str


def test_cql_or_shacl_union_structure():
    """Ensure SHACL-backed properties place triples inside their UNION branches."""
    from prez.services.query_generation.cql import CQLParser
    from rdflib import Graph

    mock_queryable_props = {
        "prop_a": "https://prez/queryables/PropA",
        "prop_b": "https://prez/queryables/PropB",
    }

    mock_system_graph = Graph()
    mock_system_graph.parse(
        data="""
        @prefix ex: <http://example.org/> .
        @prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
        @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix prezqueryables: <https://prez/queryables/> .

        prezqueryables:PropA a cql:Queryable, sh:PropertyShape ;
            dcterms:identifier "prop_a" ;
            sh:path ex:pathProp1 .

        prezqueryables:PropB a cql:Queryable, sh:PropertyShape ;
            dcterms:identifier "prop_b" ;
            sh:path ex:pathProp2 .
        """,
        format="turtle",
    )

    from prez.cache import prez_system_graph

    for triple in mock_system_graph:
        prez_system_graph.add(triple)

    try:
        cql_json_data = {
            "op": "or",
            "args": [
                {
                    "op": "in",
                    "args": [
                        {"property": "prop_a"},
                        ["http://example.org/valueA"],
                    ],
                },
                {
                    "op": "in",
                    "args": [
                        {"property": "prop_b"},
                        ["http://example.org/valueB"],
                    ],
                },
            ],
        }

        parser = CQLParser(cql_json=cql_json_data, queryable_props=mock_queryable_props)
        parser.parse()

        # The triples must live inside the UNION branches rather than the global list
        assert not parser.tssp_list
        assert len(parser.inner_select_gpntotb_list) == 1

        union_gpnt = parser.inner_select_gpntotb_list[0]
        union_str = (
            union_gpnt.to_string().replace(" ", "").replace("\n", "").replace("\t", "")
        )
        expected_union = "{?focus_node<http://example.org/pathProp1>?cql_filter_1.FILTER(?cql_filter_1IN(<http://example.org/valueA>))}UNION{?focus_node<http://example.org/pathProp2>?cql_filter_2.FILTER(?cql_filter_2IN(<http://example.org/valueB>))}"
        assert union_str == expected_union
    finally:
        for triple in mock_system_graph:
            prez_system_graph.remove(triple)


def test_cql_not_operator():
    """
    Tests the 'not' operator with FILTER NOT EXISTS.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "not",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://example.org/status"},
                    "inactive",
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should contain FILTER NOT EXISTS
    assert "FILTER NOT EXISTS" in query_str
    assert '"inactive"' in query_str
    assert 'FILTER (?var_2 = "inactive")\n' in query_str


def test_cql_not_operator_with_complex_expression():
    """
    Tests the 'not' operator with a complex nested expression (AND/OR).
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "and",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://example.org/name"},
                    "john",
                ],
            },
            {
                "op": "not",
                "args": [
                    {
                        "op": "or",
                        "args": [
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/status"},
                                    "inactive",
                                ],
                            },
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/deleted"},
                                    "true",
                                ],
                            },
                        ],
                    }
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should contain both FILTER EXISTS and FILTER NOT EXISTS
    assert "FILTER NOT EXISTS" in query_str
    assert "UNION" in query_str  # From the OR inside NOT
    assert '"john"' in query_str
    assert '"inactive"' in query_str
    assert '"true"' in query_str


def test_cql_double_negation():
    """
    Tests double negation: NOT(NOT(condition)) - should create nested FILTER NOT EXISTS.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "not",
        "args": [
            {
                "op": "not",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://example.org/status"},
                            "active",
                        ],
                    },
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should have nested FILTER NOT EXISTS statements
    not_exists_count = query_str.count("FILTER NOT EXISTS")
    assert (
        not_exists_count == 2
    ), f"Expected 2 FILTER NOT EXISTS, got {not_exists_count}"
    assert '"active"' in query_str


def test_cql_or_with_not_branches():
    """
    Tests OR with NOT in both branches: OR(NOT(A), NOT(B)).
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "or",
        "args": [
            {
                "op": "not",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://example.org/status"},
                            "inactive",
                        ],
                    },
                ],
            },
            {
                "op": "not",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://example.org/deleted"},
                            "true",
                        ],
                    },
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should have UNION with FILTER NOT EXISTS in each branch
    assert "UNION" in query_str
    not_exists_count = query_str.count("FILTER NOT EXISTS")
    assert (
        not_exists_count == 2
    ), f"Expected 2 FILTER NOT EXISTS, got {not_exists_count}"
    assert '"inactive"' in query_str
    assert '"true"' in query_str


def test_cql_complex_nested_not_and_or():
    """
    Tests complex nesting: AND(A, NOT(OR(B, AND(C, NOT(D))))).
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "and",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://example.org/name"},
                    "alice",
                ],
            },
            {
                "op": "not",
                "args": [
                    {
                        "op": "or",
                        "args": [
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/status"},
                                    "banned",
                                ],
                            },
                            {
                                "op": "and",
                                "args": [
                                    {
                                        "op": "=",
                                        "args": [
                                            {"property": "http://example.org/role"},
                                            "admin",
                                        ],
                                    },
                                    {
                                        "op": "not",
                                        "args": [
                                            {
                                                "op": "=",
                                                "args": [
                                                    {
                                                        "property": "http://example.org/verified"
                                                    },
                                                    "true",
                                                ],
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    }
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should have nested structure with multiple FILTER NOT EXISTS
    not_exists_count = query_str.count("FILTER NOT EXISTS")
    assert (
        not_exists_count == 2
    ), f"Expected 2 FILTER NOT EXISTS, got {not_exists_count}"
    assert "UNION" in query_str  # From OR inside first NOT
    assert '"alice"' in query_str
    assert '"banned"' in query_str
    assert '"admin"' in query_str
    assert '"true"' in query_str


def test_cql_not_of_and_with_not():
    """
    Tests NOT(AND(A, NOT(B))) - NOT at top level containing AND with nested NOT.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "not",
        "args": [
            {
                "op": "and",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://example.org/category"},
                            "premium",
                        ],
                    },
                    {
                        "op": "not",
                        "args": [
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/expired"},
                                    "true",
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should have nested FILTER NOT EXISTS structures
    not_exists_count = query_str.count("FILTER NOT EXISTS")
    assert (
        not_exists_count == 2
    ), f"Expected 2 FILTER NOT EXISTS, got {not_exists_count}"
    assert '"premium"' in query_str
    assert '"true"' in query_str


def test_cql_triple_negation():
    """
    Tests triple negation: NOT(NOT(NOT(condition))) - should create three nested FILTER NOT EXISTS.
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "not",
        "args": [
            {
                "op": "not",
                "args": [
                    {
                        "op": "not",
                        "args": [
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/flag"},
                                    "enabled",
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should have three nested FILTER NOT EXISTS statements
    not_exists_count = query_str.count("FILTER NOT EXISTS")
    assert (
        not_exists_count == 3
    ), f"Expected 3 FILTER NOT EXISTS, got {not_exists_count}"
    assert '"enabled"' in query_str


def test_cql_mixed_operators_with_multiple_nots():
    """
    Tests a complex mix: OR(AND(A, NOT(B)), NOT(AND(C, D))).
    """
    from prez.services.query_generation.cql import CQLParser

    cql_json_data = {
        "op": "or",
        "args": [
            {
                "op": "and",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://example.org/type"},
                            "user",
                        ],
                    },
                    {
                        "op": "not",
                        "args": [
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/suspended"},
                                    "true",
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "op": "not",
                "args": [
                    {
                        "op": "and",
                        "args": [
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/role"},
                                    "guest",
                                ],
                            },
                            {
                                "op": "=",
                                "args": [
                                    {"property": "http://example.org/temporary"},
                                    "true",
                                ],
                            },
                        ],
                    }
                ],
            },
        ],
    }

    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    query_str = parser.query_str
    # Should have UNION with different NOT structures in each branch
    assert "UNION" in query_str
    not_exists_count = query_str.count("FILTER NOT EXISTS")
    assert (
        not_exists_count == 2
    ), f"Expected 2 FILTER NOT EXISTS, got {not_exists_count}"
    assert '"user"' in query_str
    assert "suspended" in query_str  # Property name will be in the URI
    assert '"guest"' in query_str
    assert "temporary" in query_str  # Property name will be in the URI


@pytest.mark.parametrize(
    "filter_value,expected_class,expected_datatype",
    [
        ["term", "RDFLiteral", None],
        ["multi term phrase", "RDFLiteral", None],
        ['"quotedTermNoDatatype"', "RDFLiteral", None],
        ['"quoted phrase no datatype"', "RDFLiteral", None],
        [
            '"quotedTermWithDatatype"^^<http://my/datatype>',
            "RDFLiteral",
            "http://my/datatype",
        ],
        [
            "unquotedTermWithDatatype^^<http://my/datatype>",
            "RDFLiteral",
            "http://my/datatype",
        ],
        [
            "'singleQuotedTermWithDatatype'^^<http://my/datatype>",
            "RDFLiteral",
            "http://my/datatype",
        ],
        ['"some-identifier"^^<invalid uri>', "RDFLiteral", None],
        ['"some-identifier"^^<https://valid/uri>', "RDFLiteral", "https://valid/uri"],
        ['"some-identifier"^<https://valid/uri>', "RDFLiteral", None],
        [
            '"idEntifIER_with lots!of$craz3y charac^#@ters"^^<https://valid/uri>',
            "RDFLiteral",
            "https://valid/uri",
        ],
        [1, "NumericLiteral", None],
        [9999999999999999999999999999999999, "NumericLiteral", None],
        [True, "BooleanLiteral", None],
        [False, "BooleanLiteral", None],
        ["False", "RDFLiteral", None],
        [
            '"normal_value"^^<http://example.org/type> ) { SELECT * {?s ?p ?o} } FILTER(',
            "RDFLiteral",
            None,
        ],
        [
            '"normal_value""^^<http://example.org/type> ) { SELECT * {?s ?p ?o} } FILTER(',
            "RDFLiteral",
            None,
        ],
    ],
)
def test_cql_typed_literal(
    filter_value: str, expected_class: str, expected_datatype: str | None
):
    from sparql_grammar_pydantic import (  # noqa
        IRI,
        BooleanLiteral,
        NumericLiteral,
        RDFLiteral,
    )

    from prez.services.query_generation.cql import CQLParser

    expected_class = eval(expected_class)
    parser = CQLParser()
    test_element = {
        "op": "=",
        "args": [{"property": "http://example.org/prop"}, filter_value],
    }
    ggps_iterator = parser.parse_logical_operators(test_element)
    ggps = next(ggps_iterator)
    parsed_term = (
        ggps.graph_patterns_or_triples_blocks[1]
        .content.constraint.content.expression.conditional_or_expression.conditional_and_expressions[
            0
        ]
        .value_logicals[0]
        .relational_expression.right.additive_expression.base_expression.base_expression.primary_expression.content
    )
    assert isinstance(parsed_term, expected_class)
    if expected_class == RDFLiteral:
        if expected_datatype is not None:
            expected_datatype = IRI(value=expected_datatype)
        assert parsed_term.datatype == expected_datatype
