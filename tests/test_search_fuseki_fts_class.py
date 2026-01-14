from unittest.mock import patch

from pathlib import Path

from rdflib import RDFS, Graph, URIRef, DCTERMS, RDF
from sparql_grammar_pydantic import (
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    TriplesBlock,
    Var,
    TriplesSameSubjectPath,
    IRI,
)

from prez.enums import SearchMethod
from prez.services.query_generation.search_fuseki_fts import SearchQueryFusekiFTS
from prez.services.query_generation.shacl import PropertyShape


def test_query_gen():
    query_obj = SearchQueryFusekiFTS(
        term="test", limit=10, offset=0, non_shacl_predicates=[RDFS.label, RDFS.comment]
    )
    query_string = query_obj.to_string()
    print(query_string)


def test_combo_query_gen():
    """test can union the property shape inverse sequence paths etc."""
    file = Path(__file__).parent.parent / "test_data" / "fts_property_shapes.ttl"
    ps_g = Graph().parse(file)
    ps1 = PropertyShape(
        uri=URIRef("http://example.com/FTSInverseSequenceShape"),
        graph=ps_g,
        kind="fts",  # "profile" would expand these out to plain triple pattern matches
        focus_node=Var(value="focus_node"),
        shape_number=100,
    )
    ps2 = PropertyShape(
        uri=URIRef("http://example.com/FTSSequenceShape"),
        graph=ps_g,
        kind="fts",  # "profile" would expand these out to plain triple pattern matches
        focus_node=Var(value="focus_node"),
        shape_number=101,
    )
    tspp_lists = [ps1.tssp_list, ps2.tssp_list]

    ggp_list = []
    for inner_list in tspp_lists:
        ggp_list.append(
            GroupGraphPattern(
                content=GroupGraphPatternSub(
                    triples_block=TriplesBlock.from_tssp_list(inner_list)
                )
            )
        )
    gougp = GroupOrUnionGraphPattern(group_graph_patterns=ggp_list)
    assert gougp


def test_bnode_filter():
    tssp_list = [
        TriplesSameSubjectPath.from_spo(
            Var(value="focus_node"),
            IRI(value="http://example.com/hasFeatureOfInterest"),
            Var(value="path_node_1"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_1"),
            IRI(value="http://example.com/hasMember"),
            Var(value="path_node_2"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_2"),
            IRI(value="http://www.w3.org/2000/01/rdf-schema#label"),
            Var(value="fts_search_node"),
        ),
    ]
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        non_shacl_predicates=[RDFS.label, RDFS.comment],
        shacl_tssp_preds=[(tssp_list, [RDFS.label])],
    )
    query_string = query_obj.to_string()
    assert "FILTER (! isBLANK(?focus_node))" in query_string


def test_oomp():
    tssp_list = [
        TriplesSameSubjectPath.from_spo(
            Var(value="focus_node"),
            IRI(value=DCTERMS.hasPart),
            Var(value="path_node_1"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_1"),
            IRI(value=DCTERMS.hasPart),
            Var(value="path_node_2"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_2"),
            IRI(value=RDF.value),
            Var(value="fts_search_node"),
        ),
    ]
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        shacl_tssp_preds=[(tssp_list, [RDF.value])],
    )
    query_string = query_obj.to_string()
    assert "FILTER (! isBLANK(?focus_node))" in query_string


@patch("prez.dependencies.settings")
def test_one_or_more_path(mock_settings, client):
    mock_settings.search_method = SearchMethod.FTS_FUSEKI
    r = client.get("/search?q=test&predicates=oomp&_mediatype=application/sparql-query")
    assert r.status_code == 200


def test_fts_limit_none():
    """Test that when fts_limit is None, no limit is added to the text:query"""
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        non_shacl_predicates=[RDFS.label, RDFS.comment],
        fts_limit=None,
    )
    query_string = query_obj.to_string()

    # The query should contain the search term but NOT a numeric limit after it
    # Pattern: (<pred1> <pred2> "test") - no third element
    assert '<http://www.w3.org/2000/01/rdf-schema#label>' in query_string
    assert '<http://www.w3.org/2000/01/rdf-schema#comment>' in query_string
    assert '"test"' in query_string

    # Count occurrences - should have predicates and search term, but no additional numeric value
    # in the text:query parameter list
    lines = query_string.split('\n')
    text_query_section = '\n'.join([line for line in lines if 'text#query' in line or 'test' in line])

    # Should NOT have a standalone integer after the search term in the collection
    # This is a bit fragile but checks that we don't have ") 11" or similar patterns
    # that would indicate a limit parameter
    assert ') 11' not in query_string  # 10 + 1 from limit increment


def test_fts_limit_set():
    """Test that when fts_limit is set to an integer, it's added to the text:query"""
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        non_shacl_predicates=[RDFS.label, RDFS.comment],
        fts_limit=50,
    )
    query_string = query_obj.to_string()

    # The query should contain the search term AND the fts_limit value
    assert '<http://www.w3.org/2000/01/rdf-schema#label>' in query_string
    assert '<http://www.w3.org/2000/01/rdf-schema#comment>' in query_string
    assert '"test"' in query_string
    assert '50' in query_string  # The fts_limit value should appear as a numeric literal

    # Verify it's not accidentally using limit + offset
    assert 'LIMIT 11' in query_string  # The outer LIMIT should be 11 (10 + 1)
    # The FTS limit should be 50, not 10 or 11
    # Check that the text:query contains 50
    assert '"test"50' in query_string or '"test" 50' in query_string.replace('\n', ' ')


def test_fts_limit_with_shacl():
    """Test that fts_limit works correctly with SHACL predicates too"""
    tssp_list = [
        TriplesSameSubjectPath.from_spo(
            Var(value="focus_node"),
            IRI(value="http://example.com/hasFeatureOfInterest"),
            Var(value="path_node_1"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_1"),
            IRI(value="http://www.w3.org/2000/01/rdf-schema#label"),
            Var(value="fts_search_node"),
        ),
    ]

    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=5,
        shacl_tssp_preds=[(tssp_list, [RDFS.label])],
        fts_limit=100,
    )
    query_string = query_obj.to_string()

    # Should have the fts_limit value
    assert '100' in query_string
    assert '"test"' in query_string

    # Should NOT have limit + offset (which would be 15)
    # Note: the outer limit will be 11 (10+1), offset will be 5
    # But the FTS limit should be exactly 100
    assert 'LIMIT 11' in query_string  # outer limit
    assert 'OFFSET 5' in query_string  # outer offset


def test_fts_limit_default_none():
    """Test that fts_limit defaults to None when not specified"""
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        non_shacl_predicates=[RDFS.label],
        # fts_limit not specified - should default to None
    )
    query_string = query_obj.to_string()

    # Should work the same as explicitly passing None
    assert '<http://www.w3.org/2000/01/rdf-schema#label>' in query_string
    assert '"test"' in query_string
