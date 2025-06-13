from rdflib import Graph, URIRef, RDF, Namespace, Literal, XSD
from sparql_grammar_pydantic import (
    IRI,
    TriplesSameSubjectPath,
    Var,
    BooleanLiteral,
    NumericLiteral,
    RDFLiteral,
)

from prez.services.query_generation.shacl import PropertyShape

SOSA = Namespace("http://www.w3.org/ns/sosa/")
EX = Namespace("http://example.com/")
SH = Namespace("http://www.w3.org/ns/shacl#")


def test_filter_shape_sosa_style_property_chain():
    """
    Tests a property shape with a filter shape that uses a property chain.
    The filter condition is on a sibling property of the focus node.
    The SHACL pattern with an inverse path in the filter is based on documentation. This test assumes
    the implementation correctly interprets this pattern to apply the filter to the focus node.
    """
    g = Graph()
    g.bind("sh", SH)
    g.bind("sosa", SOSA)
    g.bind("rdf", RDF)
    g.bind("ex", EX)
    g.parse(
        data="""
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix ex: <http://example.com/> .

    <http://example-profile> sh:property [
        sh:path ( sosa:hasResult rdf:value ) ;
        sh:filterShape [
            sh:property [
                # The path here is the inverse of the main path.
                # This is a pattern to indicate the filter applies to a sibling property of the main path's subject.
                sh:path ( [ sh:inversePath rdf:value ] [ sh:inversePath sosa:hasResult ] ) ;
                sh:property [
                    sh:path sosa:observedProperty ;
                    sh:hasValue ex:SomeObservableProperty
                ]
            ]
        ]
    ].
    """,
        format="turtle",
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)

    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )

    # Expected triples in the WHERE clause.
    # The implementation should flatten the filter shape's logic so that it applies to the focus node.

    # 1. The filter condition from the nested property shape
    filter_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.observedProperty),
        object=IRI(value=EX.SomeObservableProperty),
    )

    # 2. The main property path
    path_triple_1 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.hasResult),
        object=Var(value="prof_1_node_1"),
    )
    path_triple_2 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="prof_1_node_1"),
        predicate=IRI(value=RDF.value),
        object=Var(value="prof_1_node_2"),
    )

    # The order is not guaranteed, so check for presence
    tssp_strings = {tssp.to_string() for tssp in ps.tssp_list}
    for expected in [filter_triple, path_triple_1, path_triple_2]:
        assert expected.to_string() in tssp_strings


def test_filter_shape_has_value_uri():
    g = Graph()
    g.bind("sh", SH)
    g.bind("sosa", SOSA)
    g.bind("rdf", RDF)
    g.bind("ex", EX)
    g.parse(
        data="""
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix ex: <http://example.com/> .

    <http://example-profile> sh:property [
        sh:path sosa:hasResult;
        sh:filterShape [
            sh:property [
                sh:path ( [ sh:inversePath sosa:hasResult ] ) ;
                sh:property [
                    sh:path sosa:observedProperty ;
                    sh:hasValue ex:SomeObservableProperty
                ]
            ]
        ]
    ].
    """,
        format="turtle",
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    filter_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.observedProperty),
        object=IRI(value=EX.SomeObservableProperty),
    )
    path_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.hasResult),
        object=Var(value="prof_1_node_1"),
    )
    tssp_strings = {tssp.to_string() for tssp in ps.tssp_list}
    assert filter_triple.to_string() in tssp_strings
    assert path_triple.to_string() in tssp_strings


def test_filter_shape_has_value_boolean():
    g = Graph()
    g.bind("sh", SH)
    g.bind("sosa", SOSA)
    g.bind("rdf", RDF)
    g.bind("ex", EX)
    g.parse(
        data="""
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix ex: <http://example.com/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    <http://example-profile> sh:property [
        sh:path sosa:hasResult;
        sh:filterShape [
            sh:property [
                sh:path ( [ sh:inversePath sosa:hasResult ] ) ;
                sh:property [
                    sh:path ex:someBooleanProperty ;
                    sh:hasValue "true"^^xsd:boolean
                ]
            ]
        ]
    ].
    """,
        format="turtle",
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    filter_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=EX.someBooleanProperty),
        object=BooleanLiteral(value=True),
    )
    path_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.hasResult),
        object=Var(value="prof_1_node_1"),
    )
    tssp_strings = {tssp.to_string() for tssp in ps.tssp_list}
    assert filter_triple.to_string() in tssp_strings
    assert path_triple.to_string() in tssp_strings


def test_filter_shape_has_value_integer():
    g = Graph()
    g.bind("sh", SH)
    g.bind("sosa", SOSA)
    g.bind("rdf", RDF)
    g.bind("ex", EX)
    g.parse(
        data="""
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix ex: <http://example.com/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    <http://example-profile> sh:property [
        sh:path sosa:hasResult;
        sh:filterShape [
            sh:property [
                sh:path ( [ sh:inversePath sosa:hasResult ] ) ;
                sh:property [
                    sh:path ex:someIntegerProperty ;
                    sh:hasValue "42"^^xsd:integer
                ]
            ]
        ]
    ].
    """,
        format="turtle",
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    filter_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=EX.someIntegerProperty),
        object=NumericLiteral(value=42),
    )
    path_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.hasResult),
        object=Var(value="prof_1_node_1"),
    )
    tssp_strings = {tssp.to_string() for tssp in ps.tssp_list}
    assert filter_triple.to_string() in tssp_strings
    assert path_triple.to_string() in tssp_strings


def test_filter_shape_has_value_decimal():
    g = Graph()
    g.bind("sh", SH)
    g.bind("sosa", SOSA)
    g.bind("rdf", RDF)
    g.bind("ex", EX)
    g.parse(
        data="""
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix ex: <http://example.com/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    <http://example-profile> sh:property [
        sh:path sosa:hasResult;
        sh:filterShape [
            sh:property [
                sh:path ( [ sh:inversePath sosa:hasResult ] ) ;
                sh:property [
                    sh:path ex:someDecimalProperty ;
                    sh:hasValue "3.14"^^xsd:decimal
                ]
            ]
        ]
    ].
    """,
        format="turtle",
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    filter_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=EX.someDecimalProperty),
        object=NumericLiteral(value=3.14),
    )
    path_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.hasResult),
        object=Var(value="prof_1_node_1"),
    )
    tssp_strings = {tssp.to_string() for tssp in ps.tssp_list}
    assert filter_triple.to_string() in tssp_strings
    assert path_triple.to_string() in tssp_strings


def test_filter_shape_has_value_string():
    g = Graph()
    g.bind("sh", SH)
    g.bind("sosa", SOSA)
    g.bind("rdf", RDF)
    g.bind("ex", EX)
    g.parse(
        data="""
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix ex: <http://example.com/> .

    <http://example-profile> sh:property [
        sh:path sosa:hasResult;
        sh:filterShape [
            sh:property [
                sh:path ( [ sh:inversePath sosa:hasResult ] ) ;
                sh:property [
                    sh:path ex:someStringProperty ;
                    sh:hasValue "hello"
                ]
            ]
        ]
    ].
    """,
        format="turtle",
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    filter_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=EX.someStringProperty),
        object=RDFLiteral(value="hello"),
    )
    path_triple = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=SOSA.hasResult),
        object=Var(value="prof_1_node_1"),
    )
    tssp_strings = {tssp.to_string() for tssp in ps.tssp_list}
    assert filter_triple.to_string() in tssp_strings
    assert path_triple.to_string() in tssp_strings
