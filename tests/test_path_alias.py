import pytest
from rdflib import DCTERMS, PROV, RDF, SH, SKOS, Graph, Namespace, URIRef
from sparql_grammar_pydantic import Var

from prez.services.query_generation.shacl import Path, PropertyShape, SequencePath

# Define SHEXT namespace locally for tests - corrected namespace
SHEXT = Namespace("http://example.com/shacl-extension#")


def test_path_alias_simple_path_on_shape():
    """Tests shext:pathAlias defined directly on the property shape BNode with a simple path."""
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path dcterms:title ;
        shext:pathAlias <https://alias/title> ;
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.and_property_paths) == 1
    assert ps.and_property_paths[0].path_alias == URIRef("https://alias/title")
    assert isinstance(ps.and_property_paths[0], Path)
    assert ps.and_property_paths[0].value == DCTERMS.title


def test_path_alias_sequence_path_on_shape():
    """Tests shext:pathAlias defined directly on the property shape BNode with a sequence path."""
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path ( prov:qualifiedDerivation prov:hadRole ) ;
        shext:pathAlias <https://alias/derivation-role> ;
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.and_property_paths) == 1
    assert ps.and_property_paths[0].path_alias == URIRef("https://alias/derivation-role")
    assert isinstance(ps.and_property_paths[0], SequencePath)
    assert len(ps.and_property_paths[0].value) == 2


def test_path_alias_in_union_simple_path():
    """Tests shext:pathAlias adjacent to a nested sh:path within sh:union."""
    g = Graph().parse(
        data="""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path [
            sh:union (
                dcterms:title
                [
                    sh:path skos:prefLabel ;
                    shext:pathAlias <https://alias/prefLabel> ;
                ]
            )
        ]
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.union_property_paths) == 2

    # Find the paths based on their value
    title_path = next((p for p in ps.union_property_paths if isinstance(p, Path) and p.value == DCTERMS.title), None)
    label_path = next((p for p in ps.union_property_paths if isinstance(p, Path) and p.value == SKOS.prefLabel), None)

    assert title_path is not None
    assert title_path.path_alias is None

    assert label_path is not None
    assert label_path.path_alias == URIRef("https://alias/prefLabel")


def test_path_alias_in_union_sequence_path():
    """Tests shext:pathAlias adjacent to a nested sequence sh:path within sh:union."""
    g = Graph().parse(
        data="""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path [
            sh:union (
                skos:prefLabel # No alias
                [
                    sh:path ( prov:qualifiedDerivation prov:hadRole ) ;
                    shext:pathAlias <https://alias/derivation-role> ;
                ]
            )
        ]
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.union_property_paths) == 2

    # Find the paths
    label_path = next((p for p in ps.union_property_paths if isinstance(p, Path) and p.value == SKOS.prefLabel), None)
    sequence_path = next((p for p in ps.union_property_paths if isinstance(p, SequencePath)), None)

    assert label_path is not None
    assert label_path.path_alias is None

    assert sequence_path is not None
    assert sequence_path.path_alias == URIRef("https://alias/derivation-role")
    assert len(sequence_path.value) == 2
    assert isinstance(sequence_path.value[0], Path)
    assert sequence_path.value[0].value == PROV.qualifiedDerivation
    assert isinstance(sequence_path.value[1], Path)
    assert sequence_path.value[1].value == PROV.hadRole
