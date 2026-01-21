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
    # For non-shacl predicates, just the bnode filter
    assert "FILTER (! isBLANK(?focus_node))" in query_string


def test_shacl_path_optional_and_bound_filter():
    """Test that SHACL path triples are wrapped in OPTIONAL with FILTER(BOUND && !isBLANK)."""
    tssp_list = [
        TriplesSameSubjectPath.from_spo(
            Var(value="fts_search_node_3"),
            IRI(value="https://linked.data.gov.au/dataset/gswa/hasAgeName"),
            Var(value="fts_search_node"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="fts_search_node_2"),
            IRI(value="https://schema.org/maxValue"),
            Var(value="fts_search_node_3"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="fts_search_node_1"),
            IRI(value="http://www.w3.org/ns/sosa/hasResult"),
            Var(value="fts_search_node_2"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="fts_search_node_1"),
            IRI(value="http://www.w3.org/ns/sosa/hasFeatureOfInterest"),
            Var(value="focus_node"),
        ),
    ]
    query_obj = SearchQueryFusekiFTS(
        term="MN02",
        limit=10,
        offset=0,
        shacl_tssp_preds=[(tssp_list, [RDFS.label])],
        fts_limit=500,
    )
    query_string = query_obj.to_string()

    # Verify OPTIONAL is present (SHACL path triples should be in OPTIONAL block)
    assert "OPTIONAL {" in query_string

    # Verify the combined FILTER with BOUND and !isBLANK
    assert "FILTER (BOUND(?focus_node) && ! isBLANK(?focus_node))" in query_string

    # Verify the triple patterns are present
    assert "https://linked.data.gov.au/dataset/gswa/hasAgeName" in query_string
    assert "https://schema.org/maxValue" in query_string
    assert "http://www.w3.org/ns/sosa/hasResult" in query_string
    assert "http://www.w3.org/ns/sosa/hasFeatureOfInterest" in query_string


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
    # SHACL paths use OPTIONAL + FILTER(BOUND && !isBLANK)
    assert "OPTIONAL {" in query_string
    assert "FILTER (BOUND(?focus_node) && ! isBLANK(?focus_node))" in query_string


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
    """Test that when fts_limit is set (offset=0), it's added to the text:query."""
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        non_shacl_predicates=[RDFS.label, RDFS.comment],
        fts_limit=50,
    )
    query_string = query_obj.to_string()

    assert '<http://www.w3.org/2000/01/rdf-schema#label>' in query_string
    assert '<http://www.w3.org/2000/01/rdf-schema#comment>' in query_string
    assert '"test"' in query_string

    # Outer LIMIT should be 11 (10 + 1)
    assert 'LIMIT 11' in query_string

    # FTS numeric limit should be exactly 50 when offset=0
    assert '"test"50' in query_string or '"test" 50' in query_string.replace('\n', ' ')


def test_fts_limit_adds_offset_non_shacl():
    """Test the FTS numeric limit uses fts_limit + offset (non-SHACL predicates case)."""
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=7,
        non_shacl_predicates=[RDFS.label],
        fts_limit=50,
    )
    query_string = query_obj.to_string()

    assert 'OFFSET 7' in query_string
    assert 'LIMIT 11' in query_string

    # FTS numeric limit should be 50 + 7
    assert '57' in query_string
    assert '50' not in query_string
    assert '"test"57' in query_string or '"test" 57' in query_string.replace('\n', ' ')


def test_fts_limit_with_shacl():
    """Test that FTS numeric limit is fts_limit + offset when offset is provided (SHACL path case)."""
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

    # Outer pagination
    assert 'LIMIT 11' in query_string
    assert 'OFFSET 5' in query_string

    # FTS numeric limit should be fts_limit + offset (100 + 5)
    assert '105' in query_string
    assert '100' not in query_string
    assert '"test"105' in query_string or '"test" 105' in query_string.replace('\n', ' ')


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
