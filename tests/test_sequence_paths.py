from rdflib import Graph, URIRef
from rdflib.namespace import SH
from sparql_grammar_pydantic import PathAlternative, PathEltOrInverse, Var

from prez.services.query_generation.shacl import (
    AlternativePath,
    Path,
    PropertyShape,
    SequencePath,
    _build_path_elt_or_inverse,
)


def test_build_path_elt_or_inverse_handles_sequence_path():
    """Ensure SequencePath is converted to a PathEltOrInverse instead of raising."""
    seq_path = SequencePath(
        value=[
            Path(value=URIRef("http://example.com/p1")),
            Path(value=URIRef("http://example.com/p2")),
        ]
    )

    path_elt_or_inverse = _build_path_elt_or_inverse(seq_path)

    assert isinstance(path_elt_or_inverse, PathEltOrInverse)
    path_alt = path_elt_or_inverse.path_elt.path_primary.value.path_alternative
    assert isinstance(path_alt, PathAlternative)
    assert len(path_alt.sequence_paths) == 1
    assert len(path_alt.sequence_paths[0].list_path_elt_or_inverse) == 2


def test_property_shape_handles_sequence_path_in_alternative():
    """Instantiate a PropertyShape with alternative path made of SequencePaths (inline turtle)."""
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX ex: <http://example.com/>

        <http://example-profile> sh:property [
            sh:path [
                sh:alternativePath (
                    ( ex:p1 ex:p2 )
                    ( ex:p3 ex:p4 )
                )
            ] ;
        ] .
        """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )

    alt_path = ps.and_property_paths[0]
    assert isinstance(alt_path, AlternativePath)
    # Each alternative should be a SequencePath with two predicates
    assert all(isinstance(p, SequencePath) for p in alt_path.value)
    assert all(len(p.value) == 2 for p in alt_path.value)
