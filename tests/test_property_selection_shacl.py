import pytest
from rdflib import DCTERMS, PROV, RDF, SH, Graph, URIRef
from sparql_grammar_pydantic import (
    IRI,
    Filter,
    GroupOrUnionGraphPattern,
    OptionalGraphPattern,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
)

from prez.reference_data.prez_ns import REG
from prez.services.query_generation.shacl import PropertyShape


def test_simple_path():
    g = Graph().parse(
        data="""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>

    <http://example-profile> sh:property [ sh:path rdf:type ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert (
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=RDF.type),
                object=Var(value="prof_1_node_1"),
            )
            in ps.tssp_list
    )


def test_sequence_path():
    g = Graph().parse(
        data="""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>

    <http://example-profile> sh:property [ sh:path ( prov:qualifiedDerivation prov:hadRole ) ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert (
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=PROV.qualifiedDerivation),
                object=Var(value="prof_1_node_1"),
            )
            in ps.tssp_list
    )
    assert (
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="prof_1_node_1"),
                predicate=IRI(value=PROV.hadRole),
                object=Var(value="prof_1_node_2"),
            )
            in ps.tssp_list
    )


def test_union():
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>

    <http://example-profile> sh:property [
        sh:path [
            sh:union (
              dcterms:publisher
              reg:status
              ( prov:qualifiedDerivation prov:hadRole )
              ( prov:qualifiedDerivation prov:entity )
            )
          ]
        ]
    .

    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=PROV.qualifiedDerivation),
                object=Var(value="prof_1_node_3"),
            )
            in ps.tss_list
    )
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="prof_1_node_3"),
                predicate=IRI(value=PROV.hadRole),
                object=Var(value="prof_1_node_4"),
            )
            in ps.tss_list
    )
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=PROV.qualifiedDerivation),
                object=Var(value="prof_1_node_5"),
            )
            in ps.tss_list
    )
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="prof_1_node_5"),
                predicate=IRI(value=PROV.entity),
                object=Var(value="prof_1_node_6"),
            )
            in ps.tss_list
    )
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=DCTERMS.publisher),
                object=Var(value="prof_1_node_1"),
            )
            in ps.tss_list
    )
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=REG.status),
                object=Var(value="prof_1_node_2"),
            )
            in ps.tss_list
    )


def test_optional_props():
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>

    <http://example-profile> sh:property [
        sh:minCount 0 ;
        sh:path dcterms:publisher ;
        ]
    .

    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert ps.tssp_list == []
    assert isinstance(ps.gpnt_list[0].content, OptionalGraphPattern)


def test_complex_optional_props():
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>

    <http://example-profile> sh:property [
        sh:minCount 0 ;
        sh:path dcterms:publisher , ( prov:qualifiedDerivation prov:hadRole )
        ]
    .

    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert ps.tssp_list == []
    assert isinstance(ps.gpnt_list[0].content, OptionalGraphPattern)


def test_excluded_props():
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>

    <http://example-profile> sh:property [
        sh:maxCount 0 ;
        sh:path dcterms:publisher , reg:status
        ]
    .

    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert (
            TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=Var(value="preds"),
                object=Var(value="excluded_pred_vals"),
            )
            in ps.tssp_list
    )
    assert isinstance(ps.gpnt_list[0].content, Filter)


@pytest.mark.parametrize(
    ["cardinality_type", "expected_result"],
    [
        (
                "sh:zeroOrMorePath",
                "?focus_node <http://purl.org/dc/terms/publisher>* ?prof_1_node_1",
        ),
        (
                "sh:oneOrMorePath",
                "?focus_node <http://purl.org/dc/terms/publisher>+ ?prof_1_node_1",
        ),
        (
                "sh:zeroOrOnePath",
                "?focus_node <http://purl.org/dc/terms/publisher>? ?prof_1_node_1",
        ),
    ],
)
def test_cardinality_props(cardinality_type, expected_result):
    g = Graph().parse(
        data=f"""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX sh: <http://www.w3.org/ns/shacl#>

    <http://example-profile> sh:property [
        sh:path [ {cardinality_type} dcterms:publisher ] ;
        ]
    .

    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert ps.tssp_list[0].to_string() == expected_result


def test_bnode_depth_union():
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX shext: <http://example.com/shacl-extension#>

    <http://example-profile> sh:property [
        sh:path [
            sh:union (
              [ shext:bNodeDepth "2" ]
            )
          ]
        ]
    .
    """)
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    expected_output = "".join("""
    {
        ?focus_node ?bn_p_1 ?bn_o_1 .
        ?bn_o_1 ?bn_p_2 ?bn_o_2
        FILTER isBLANK(?bn_o_1)
    }
    UNION
    {
        ?focus_node ?bn_p_1 ?bn_o_1 .
        ?bn_o_1 ?bn_p_2 ?bn_o_2 .
        ?bn_o_2 ?bn_p_3 ?bn_o_3
        FILTER isBLANK(?bn_o_1)
        FILTER isBLANK(?bn_o_2)
    }""".split())
    actual_output = "".join(ps.gpnt_list[0].to_string().split())
    assert actual_output == expected_output


def test_bnode_depth_direct():
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX shext: <http://example.com/shacl-extension#>

    <http://example-profile> sh:property [
        sh:path [ shext:bNodeDepth "2" ]
        ]
    .
    """)
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    expected_output = "".join("""
    {
        ?focus_node ?bn_p_1 ?bn_o_1 .
        ?bn_o_1 ?bn_p_2 ?bn_o_2
        FILTER isBLANK(?bn_o_1)
    }
    UNION
    {
        ?focus_node ?bn_p_1 ?bn_o_1 .
        ?bn_o_1 ?bn_p_2 ?bn_o_2 .
        ?bn_o_2 ?bn_p_3 ?bn_o_3
        FILTER isBLANK(?bn_o_1)
        FILTER isBLANK(?bn_o_2)
    }""".split())
    actual_output = "".join(ps.gpnt_list[0].to_string().split())
    assert actual_output == expected_output


def test_bnode_depth_profile_depth():
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX shext: <http://example.com/shacl-extension#>

    <http://example-profile> sh:property [
        sh:path [ shext:bNodeDepth "25" ]
        ]
    .
    """)
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    # output is extremely long, just attempt to generate the property shape; syntax is tested in two prior tests.


def test_union_nested_bnode():
    """Tests sh:union containing the new optional nested BNode structure with sh:path."""
    g = Graph().parse(
        data="""
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX shext: <https://linked.data.gov.au/def/shacl-extensions/>

    <http://example-profile> sh:property [
        sh:path [
            sh:union (
              # Regular path
              dcterms:publisher
              # Nested BNode with direct path
              [
                sh:path reg:status ;
                shext:pathAlias <https://my-shorthand-property/status> ; # Should be ignored
                shext:facet true ;                                # Should be ignored
              ]
              # Nested BNode with sequence path
              [
                sh:path ( prov:qualifiedDerivation prov:hadRole ) ;
                shext:pathAlias <https://my-shorthand-property/derivation-role> ; # Ignored
              ]
              # Regular inverse path
              [ sh:inversePath dcterms:creator ]
              [
                sh:path [ sh:inversePath <https://imaginary-prop> ] ;
                shext:pathAlias <https://forward-prop-for-inverse> ; # Ignored
              ]
            )
          ]
        ]
    .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )

    # Check that the triples generated for the CONSTRUCT clause (tss_list) are correct
    # The variable numbering depends on the order paths are processed within the union list.

    # 1. dcterms:publisher (direct)
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=DCTERMS.publisher),
                object=Var(value="prof_1_node_1"),
            )
            in ps.tss_list
    )

    # 2. reg:status (from nested BNode)
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=REG.status),
                object=Var(value="prof_1_node_2"),
            )
            in ps.tss_list
    )

    # 3. ( prov:qualifiedDerivation prov:hadRole ) (from nested BNode)
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=PROV.qualifiedDerivation),
                object=Var(value="prof_1_node_3"),
            )
            in ps.tss_list
    )
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="prof_1_node_3"),
                predicate=IRI(value=PROV.hadRole),
                object=Var(value="prof_1_node_4"),
            )
            in ps.tss_list
    )

    # 4. [ sh:inversePath dcterms:creator ] (direct inverse)
    assert (
            TriplesSameSubject.from_spo(
                subject=Var(value="prof_1_node_5"),
                predicate=IRI(value=DCTERMS.creator),
                object=Var(value="focus_node"),
            )
            in ps.tss_list
    )

    # Also check the WHERE clause paths (tssp_list) are generated correctly within the UNION structure
    # The gpnt_list should contain one GroupOrUnionGraphPattern
    assert len(ps.gpnt_list) == 1
    union_pattern = ps.gpnt_list[0].content
    assert isinstance(union_pattern, GroupOrUnionGraphPattern)
    assert len(union_pattern.group_graph_patterns) == 5 # One group for each path in the union

    # Check structure of generated WHERE clause patterns (simplified check)
    # Note: Comparing strings directly can be brittle due to formatting variations.
    # A more robust approach might involve parsing the string back into a structure or comparing graph patterns directly.
    # However, for now, we adjust the expected string format based on observed output.

    # Pattern 1: dcterms:publisher
    expected_pattern_1 = """{
?focus_node <http://purl.org/dc/terms/publisher> ?prof_1_node_1
}"""
    assert union_pattern.group_graph_patterns[0].to_string().strip() == expected_pattern_1.strip()

    # Pattern 2: reg:status
    expected_pattern_2 = """{
?focus_node <http://purl.org/linked-data/registry#status> ?prof_1_node_2
}"""
    assert union_pattern.group_graph_patterns[1].to_string().strip() == expected_pattern_2.strip()

    # Pattern 3: ( prov:qualifiedDerivation prov:hadRole )
    expected_pattern_3 = """{
?prof_1_node_3 <http://www.w3.org/ns/prov#hadRole> ?prof_1_node_4 .
?focus_node <http://www.w3.org/ns/prov#qualifiedDerivation> ?prof_1_node_3

}"""
    assert union_pattern.group_graph_patterns[2].to_string().strip() == expected_pattern_3.strip()

    # Pattern 4: inverse(dcterms:creator)
    expected_pattern_4 = """{
?prof_1_node_5 <http://purl.org/dc/terms/creator> ?focus_node
}"""
    assert union_pattern.group_graph_patterns[3].to_string().strip() == expected_pattern_4.strip()
