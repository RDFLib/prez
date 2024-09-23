import pytest
from rdflib import Graph, URIRef, SH, RDF, PROV, DCTERMS

from prez.reference_data.prez_ns import REG
from prez.services.query_generation.shacl import PropertyShape
from sparql_grammar_pydantic import (
    Var,
    IRI,
    OptionalGraphPattern,
    Filter,
    TriplesSameSubjectPath, TriplesSameSubject,
)


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
        sh:path (
            sh:union (
              dcterms:publisher
              reg:status
              ( prov:qualifiedDerivation prov:hadRole )
              ( prov:qualifiedDerivation prov:entity )
            )
          )
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
        ("sh:zeroOrMorePath", '?focus_node <http://purl.org/dc/terms/publisher>* ?prof_1_node_1'),
        ("sh:oneOrMorePath", '?focus_node <http://purl.org/dc/terms/publisher>+ ?prof_1_node_1'),
        ("sh:zeroOrOnePath", '?focus_node <http://purl.org/dc/terms/publisher>? ?prof_1_node_1'),
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
