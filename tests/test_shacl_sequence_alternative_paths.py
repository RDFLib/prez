from unittest.mock import patch

import pytest
from rdflib import DCTERMS, PROV, RDF, RDFS, SH, Graph, Namespace, URIRef, SKOS
from sparql_grammar_pydantic import (
    IRI,
    TriplesSameSubject,
    Var,
)

from prez.services.query_generation.shacl import PropertyShape

# Define SHEXT namespace locally for tests
SHEXT = Namespace("http://example.com/shacl-extension#")
EX = Namespace("http://example.com/ns#")


def normalize_sparql(sparql_string):
    """Helper function to normalize SPARQL strings for comparison."""
    return "".join(sparql_string.split()).strip()


@pytest.fixture
def focus_node_var():
    return Var(value="focus_node")


@pytest.fixture
def graph_with_prefixes():
    g = Graph()
    g.bind("sh", SH)
    g.bind("ex", EX)
    g.bind("prov", PROV)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)
    g.bind("shext", SHEXT)
    return g


def test_sequence_with_mid_alternative_endpoint_kind(focus_node_var, graph_with_prefixes):
    """
    Tests a sequence path with an alternative path segment in the middle for 'endpoint' kind.
    sh:path ( ex:p1 (ex:altA | ex:altB) ex:p2 )
    """
    g = graph_with_prefixes
    g.parse(
        data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.com/ns#> .

        <http://example-profile> sh:property [
            sh:path ( ex:p1 [ sh:alternativePath ( ex:altA ex:altB ) ] ex:p2 )
        ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="endpoint", focus_node=focus_node_var, shape_number=0
    )

    # Expected WHERE clause: a single complex path expression
    expected_tssp_string = normalize_sparql(
        f"{focus_node_var.to_string()} <{EX.p1}>/(<{EX.altA}>|<{EX.altB}>)/<{EX.p2}> ?path_node_3"
    )
    
    assert len(ps.tssp_list) == 1
    actual_tssp_string = normalize_sparql(ps.tssp_list[0].to_string())
    assert actual_tssp_string == expected_tssp_string

    # CONSTRUCT clause should be empty for non-aliased complex paths in endpoint kind
    assert len(ps.tss_list) == 0


@patch("prez.services.query_generation.shacl.settings")
def test_sequence_with_alternative_and_path_alias(mock_settings, focus_node_var, graph_with_prefixes):
    """
    Tests a sequence path with an alternative path segment and shext:pathAlias on the overall property shape.
    sh:property [ sh:path ( ex:p1 (ex:altA | ex:altB) ex:p2 ); shext:pathAlias ex:mySeqAlias ]
    """
    mock_settings.use_path_aliases = True
    g = graph_with_prefixes
    g.parse(
        data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.com/ns#> .
        @prefix shext: <http://example.com/shacl-extension#> .

        <http://example-profile> sh:property [
            sh:path ( ex:p1 [ sh:alternativePath ( ex:altA ex:altB ) ] ex:p2 ) ;
            shext:pathAlias ex:mySeqAlias ;
        ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )

    # CONSTRUCT clause: should use the alias for the whole sequence
    expected_alias_tss = TriplesSameSubject.from_spo(
        subject=focus_node_var,
        predicate=IRI(value=EX.mySeqAlias),
        object=Var(value="prof_1_node_3"), # Final node of the sequence
    )
    assert expected_alias_tss in ps.tss_list

    # Ensure individual components of the sequence are NOT in CONSTRUCT due to alias
    assert not any(IRI(value=EX.p1).to_string() in str(tss) for tss in ps.tss_list if tss != expected_alias_tss)
    assert not any(IRI(value=EX.altA).to_string() in str(tss) for tss in ps.tss_list if tss != expected_alias_tss)
    assert not any(IRI(value=EX.altB).to_string() in str(tss) for tss in ps.tss_list if tss != expected_alias_tss)
    assert not any(IRI(value=EX.p2).to_string() in str(tss) for tss in ps.tss_list if tss != expected_alias_tss)

    # WHERE clause: should still expand the sequence with the alternative correctly
    # This is implicitly tested by the first test case, but we can add a quick check for the overall structure.
    assert len(ps.gpnt_list) == 1


def test_sequence_with_alternative_containing_complex_elements(focus_node_var, graph_with_prefixes):
    """
    Tests a sequence path with an alternative path segment containing inverse and cardinality paths.
    sh:path ( ex:p1 [ sh:alternativePath ( [ sh:inversePath ex:invAlt ] [ sh:zeroOrMorePath ex:cardAlt ] ) ] ex:p2 )
    """
    g = graph_with_prefixes
    g.parse(
        data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.com/ns#> .

        <http://example-profile> sh:property [
            sh:path ( ex:p1 [ sh:alternativePath ( [ sh:inversePath ex:invAlt ] [ sh:zeroOrMorePath ex:cardAlt ] ) ] ex:p2 )
        ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )

    # Expected WHERE clause structure:
    # ?focus_node ex:p1 ?prof_0_node_1 .
    # { ?prof_0_node_2 ex:invAlt ?prof_0_node_1 . } UNION { ?prof_0_node_1 ex:cardAlt* ?prof_0_node_2 . }
    # ?prof_0_node_2 ex:p2 ?prof_0_node_3 .

    actual_gpnt_string = ps.gpnt_list[0].to_string()
    expected_gpnt_string = """{


{
?prof_1_node_2 <http://example.com/ns#invAlt> ?prof_1_node_1
}
UNION
{
?prof_1_node_1 <http://example.com/ns#cardAlt>* ?prof_1_node_2
}
}"""
    assert actual_gpnt_string == expected_gpnt_string

    # Check CONSTRUCT for individual triples (no alias)
    assert TriplesSameSubject.from_spo(
        subject=Var(value="prof_1_node_2"),
        predicate=IRI(value=EX.invAlt),
        object=Var(value="prof_1_node_1"),
    ) in ps.tss_list
    assert TriplesSameSubject.from_spo(
        subject=Var(value="prof_1_node_1"),
        predicate=IRI(value=EX.cardAlt), # Note: for *+? paths, the construct usually adds the simple predicate
        object=Var(value="prof_1_node_2"),
    ) in ps.tss_list
