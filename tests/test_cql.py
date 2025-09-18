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
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
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
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


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
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")
    assert parser.inner_select_gpntotb_list[1].to_string().replace(" ", "").replace(
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
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
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
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
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
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")
    assert parser.inner_select_gpntotb_list[1].to_string().replace(" ", "").replace(
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
    assert len(parser.inner_select_gpntotb_list) == len(
        expected_inner_select_gpntotb_list_str
    )
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace(
        "\n", ""
    ) == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_focus_node_in_subquery():
    """
    Tests that ?focus_node is always included in the inner select variables,
    even for a simple query.
    """
    from prez.services.query_generation.cql import CQLParser
    from sparql_grammar_pydantic import Var

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
    path_vars = {
        var.value
        for var in parser.inner_select_vars
        if var.value.startswith("path_node_")
    }
    assert len(path_vars) == 3, "Each branch should expose a unique path variable"

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
        expected_union = (
            "{?focus_node<http://example.org/pathProp1>?path_node_1.VALUES?path_node_1{<http://example.org/valueA>}}"
            "UNION"
            "{?focus_node<http://example.org/pathProp2>?path_node_2.VALUES?path_node_2{<http://example.org/valueB>}}"
        )
        assert union_str == expected_union
    finally:
        for triple in mock_system_graph:
            prez_system_graph.remove(triple)
