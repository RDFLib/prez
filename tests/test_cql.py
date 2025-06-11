import json
from pathlib import Path
from urllib.parse import quote_plus

import pytest

cql_filenames = [
    "example01.json",
    # "example02.json",
    # "example03.json",
    # "example05a.json",
    # "example05b.json",
    # "example06b.json",
    # "example09.json",
    # "example10.json",
    # "example11.json",
    # "example12.json",
    # "example14.json",
    # "example15.json",
    # "example17.json",
    # "example29.json",
    # "example31.json",
    # "example32.json",
    # "example33.json",
    # "example34.json",
    # "example35.json",
    # "example39.json",
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
?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/sosa/Sample>
}
UNION
{
?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://linked.data.gov.au/def/borehole/Bore>
}"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


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
?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/vocab#Report>"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


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
        Var(value="focus_node"),
        IRI(value=prop_uri),
        IRI(value=val_uri)
    )

def _get_all_tssp_from_triples_block(triples_block):
    """Helper to extract all TriplesSameSubjectPath from a linked list of TriplesBlock."""
    from sparql_grammar_pydantic import TriplesBlock, TriplesSameSubjectPath
    all_tssp = []
    current_block = triples_block
    while current_block:
        if isinstance(current_block, TriplesBlock) and isinstance(current_block.triples, TriplesSameSubjectPath):
            all_tssp.append(current_block.triples)
        elif isinstance(current_block, TriplesSameSubjectPath):
            all_tssp.append(current_block)
        current_block = getattr(current_block, 'triples_block', None)
    return all_tssp


def test_cql_and_of_A_or_BC():
    """Tests AND(A, OR(B, C))"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {
        "op": "and",
        "args": [
            cql_A,
            {
                "op": "or",
                "args": [cql_B, cql_C]
            }
        ]
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    where_content = parser.query_object.where_clause.group_graph_pattern.content

    expected_inner_select_gpntotb_list_str = [
        """?focus_node <http://example.org/propA> <http://example.org/valA>""",
        """
{
{
?focus_node <http://example.org/propB> <http://example.org/valB>
}
UNION
{
?focus_node <http://example.org/propC> <http://example.org/valC>
}
}"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")
    assert parser.inner_select_gpntotb_list[1].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[1].replace(" ", "").replace("\n", "")


def test_cql_or_of_A_and_BC():
    """Tests OR(A, AND(B, C))"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {
        "op": "or",
        "args": [
            cql_A,
            {
                "op": "and",
                "args": [cql_B, cql_C]
            }
        ]
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    expected_inner_select_gpntotb_list_str = [
        """

{
?focus_node <http://example.org/propA> <http://example.org/valA>
}
UNION
{
?focus_node <http://example.org/propC> <http://example.org/valC> .
?focus_node <http://example.org/propB> <http://example.org/valB>

}"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_cql_and_of_and_AB_C():
    """Tests AND(AND(A, B), C)"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {
        "op": "and",
        "args": [
            {
                "op": "and",
                "args": [cql_A, cql_B]
            },
            cql_C
        ]
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    expected_inner_select_gpntotb_list_str = [
        """?focus_node <http://example.org/propC> <http://example.org/valC> .
?focus_node <http://example.org/propB> <http://example.org/valB> .
?focus_node <http://example.org/propA> <http://example.org/valA>"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


def test_cql_or_of_or_AB_C():
    """Tests OR(OR(A, B), C)"""
    from prez.services.query_generation.cql import CQLParser

    cql_A = _create_eq_cql(PROP_A, VAL_A)
    cql_B = _create_eq_cql(PROP_B, VAL_B)
    cql_C = _create_eq_cql(PROP_C, VAL_C)

    cql_json_data = {
        "op": "or",
        "args": [
            {
                "op": "or",
                "args": [cql_A, cql_B]
            },
            cql_C
        ]
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    expected_inner_select_gpntotb_list_str = [
        """
{
{
?focus_node <http://example.org/propA> <http://example.org/valA>
}
UNION
{
?focus_node <http://example.org/propB> <http://example.org/valB>
}
}
UNION
{
?focus_node <http://example.org/propC> <http://example.org/valC>
}
"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")


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
            {"op": "or", "args": [cql_C, cql_D]}
        ]
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()
    where_content = parser.query_object.where_clause.group_graph_pattern.content

    expected_inner_select_gpntotb_list_str = [
        """
{
{
?focus_node <http://example.org/propA> <http://example.org/valA>
}
UNION
{
?focus_node <http://example.org/propB> <http://example.org/valB>
}
}""",
        """
{
{
?focus_node <http://example.org/propC> <http://example.org/valC>
}
UNION
{
?focus_node <http://example.org/propD> <http://example.org/valD>
}
}"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")
    assert parser.inner_select_gpntotb_list[1].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[1].replace(" ", "").replace("\n", "")


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
            {"op": "and", "args": [cql_C, cql_D]}
        ]
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()
    where_content = parser.query_object.where_clause.group_graph_pattern.content

    expected_inner_select_gpntotb_list_str = [
        """
{
?focus_node <http://example.org/propB> <http://example.org/valB> .
?focus_node <http://example.org/propA> <http://example.org/valA>
}
UNION
{
?focus_node <http://example.org/propD> <http://example.org/valD> .
?focus_node <http://example.org/propC> <http://example.org/valC>
}
"""
    ]
    assert len(parser.inner_select_gpntotb_list) == len(expected_inner_select_gpntotb_list_str)
    assert parser.inner_select_gpntotb_list[0].to_string().replace(" ", "").replace("\n", "") == expected_inner_select_gpntotb_list_str[0].replace(" ", "").replace("\n", "")
