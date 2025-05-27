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
    from sparql_grammar_pydantic import (
        GroupGraphPattern,
        GroupOrUnionGraphPattern,
        GraphPatternNotTriples,
        TriplesSameSubjectPath,
        Var,
    )

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
    parser.parse()

    # 1. self.tssp_list should be empty because all triples are within OR branches
    assert len(parser.tssp_list) == 0, "tssp_list should be empty for OR query"

    # 2. Check the structure of the ggps_inner_select for the UNION
    assert parser.ggps_inner_select is not None
    assert (
        parser.ggps_inner_select.graph_patterns_or_triples_blocks is not None
    ), "ggps_inner_select should have graph_patterns_or_triples_blocks"
    assert (
        len(parser.ggps_inner_select.graph_patterns_or_triples_blocks) == 1
    ), "ggps_inner_select should contain one GraphPatternNotTriples for the UNION"

    gpnt = parser.ggps_inner_select.graph_patterns_or_triples_blocks[0]
    assert isinstance(
        gpnt, GraphPatternNotTriples
    ), "The item should be a GraphPatternNotTriples"
    assert isinstance(
        gpnt.content, GroupOrUnionGraphPattern
    ), "Content of GPNT should be GroupOrUnionGraphPattern"

    union_pattern = gpnt.content
    assert (
        len(union_pattern.group_graph_patterns) == 2
    ), "GroupOrUnionGraphPattern should have two branches"

    # Check first branch of the UNION
    branch1_ggp = union_pattern.group_graph_patterns[0]
    assert isinstance(
        branch1_ggp, GroupGraphPattern
    ), "Branch 1 should be a GroupGraphPattern"
    assert branch1_ggp.content is not None
    assert branch1_ggp.content.triples_block is not None
    branch1_tssp = branch1_ggp.content.triples_block.triples
    assert isinstance(
        branch1_tssp, TriplesSameSubjectPath
    ), "Branch 1 triple should be TriplesSameSubjectPath"
    assert branch1_tssp.varorterm == Var(value="focus_node")
    assert (
        branch1_tssp.propertylist.first_pair[0].verb.iri.value
        == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    )
    assert (
        branch1_tssp.propertylist.first_pair[1].object_list.first_object.iri.value
        == "http://www.w3.org/ns/sosa/Sample"
    )

    # Check second branch of the UNION
    branch2_ggp = union_pattern.group_graph_patterns[1]
    assert isinstance(
        branch2_ggp, GroupGraphPattern
    ), "Branch 2 should be a GroupGraphPattern"
    assert branch2_ggp.content is not None
    assert branch2_ggp.content.triples_block is not None
    branch2_tssp = branch2_ggp.content.triples_block.triples
    assert isinstance(
        branch2_tssp, TriplesSameSubjectPath
    ), "Branch 2 triple should be TriplesSameSubjectPath"
    assert branch2_tssp.varorterm == Var(value="focus_node")
    assert (
        branch2_tssp.propertylist.first_pair[0].verb.iri.value
        == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    )
    assert (
        branch2_tssp.propertylist.first_pair[1].object_list.first_object.iri.value
        == "https://linked.data.gov.au/def/borehole/Bore"
    )

    # Also check self.tss_list for CONSTRUCT part (should contain both)
    assert len(parser.tss_list) == 2, "tss_list should contain two triples for CONSTRUCT"
    # Detailed check for tss_list can be added if necessary, but length check is a good start.
    # Example for one:
    # tss1 = parser.tss_list[0]
    # assert tss1.varorterm == Var(value="focus_node")
    # assert tss1.propertylist.first_pair[0].verb.iri.value == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    # assert tss1.propertylist.first_pair[1].object_list.first_object.iri.value == "http://www.w3.org/ns/sosa/Sample"
