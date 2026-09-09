from pathlib import Path

import pytest
from rdflib import Graph, URIRef, Namespace, Literal, BNode
from rdflib.namespace import SH, RDF, RDFS
from sparql_grammar import (
    IRI,
    PathAlternative,
    PathElt,
    PathEltOrInverse,
    PathPrimary,
    TriplesSameSubjectPath,
    Var,
)


from prez.services.query_generation.shacl import NodeShape

endpoints_graph = Graph().parse(
    Path(__file__).parent.parent
    / "prez/reference_data/endpoints/data_endpoints_default/default_endpoints.ttl",
    format="turtle",
)


@pytest.mark.parametrize("nodeshape_uri", ["http://example.org/shape-R0-HL2"])
def test_nodeshape_parsing(nodeshape_uri):
    ns = NodeShape(
        uri=URIRef(nodeshape_uri),
        graph=endpoints_graph,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
    )
    assert ns.targetClasses == [
        URIRef("http://www.w3.org/2004/02/skos/core#Collection"),
        URIRef("http://www.w3.org/2004/02/skos/core#ConceptScheme"),
        URIRef("http://www.w3.org/ns/dcat#Dataset"),
        URIRef("http://www.w3.org/ns/dcat#Resource"),
    ]
    assert len(ns.propertyShapesURIs) == 1


@pytest.mark.parametrize(
    "nodeshape_uri",
    ["http://example.org/shape-R0-HL3-1"],
)
def test_nodeshape_to_grammar(nodeshape_uri):
    ns = NodeShape(
        uri=URIRef(nodeshape_uri),
        graph=endpoints_graph,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
    )
    assert ns
    # Add more specific assertions based on expected grammar output if needed
    # For example, check ns.tssp_list or ns.gpnt_list


EX = Namespace("http://example.org/")


def _alternative_path_tssp(ns: NodeShape) -> TriplesSameSubjectPath | None:
    """The triple pattern whose predicate is a two-way path alternative, if any.

    The NodeShape also generates a TSSP for the sh:targetClass (rdf:type).
    """
    for tssp in ns.tssp_list:
        verb = tssp.property_list_path.pairs[0][0]
        if isinstance(verb, PathAlternative) and len(verb.sequence_paths) == 2:
            return tssp
    return None


def test_alternative_path():
    """Tests that sh:alternativePath is correctly parsed and converted to SPARQL grammar."""
    shape_ttl = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ont: <https://prez.dev/ont/> .

        ex:AltPathShape
            a sh:NodeShape ;
            sh:targetClass ex:MyClass ;
            ont:hierarchyLevel 1 ;
            sh:property [
                sh:path [ sh:alternativePath ( ex:prop1 ex:prop2 ) ] ;
                sh:name "Alternative Property" ;
            ] .
        """
    g = Graph().parse(data=shape_ttl, format="turtle")
    focus_node_var = Var(value="focus_node")
    ns = NodeShape(
        uri=EX.AltPathShape,
        graph=g,
        kind="endpoint",
        focus_node=focus_node_var,
    )

    # Expected TSSP structure for ?focus_node ex:prop1|ex:prop2 ?path_node_1 .
    expected_tssp = TriplesSameSubjectPath.from_spo(
        focus_node_var,
        PathAlternative.alt(IRI(value=EX.prop1), IRI(value=EX.prop2)),
        Var(value="path_node_1"),
    )

    alternative_path_tssp = _alternative_path_tssp(ns)
    assert (
        alternative_path_tssp is not None
    ), "Alternative path TSSP not found in NodeShape tssp_list"
    assert (
        alternative_path_tssp == expected_tssp
    ), "Generated TSSP for alternative path does not match expected structure"
    assert (
        alternative_path_tssp.to_string()
        == f"?focus_node <{EX.prop1}>|<{EX.prop2}> ?path_node_1"
    )


def test_alternative_with_inverse_path():
    """Tests sh:alternativePath containing an sh:inversePath."""
    shape_ttl = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ont: <https://prez.dev/ont/> .

        ex:AltInvPathShape
            a sh:NodeShape ;
            sh:targetClass ex:MyOtherClass ;
            ont:hierarchyLevel 1 ;
            sh:property [
                sh:path [ sh:alternativePath ( ex:prop1 [ sh:inversePath ex:prop2 ] ) ] ;
                sh:name "Alternative with Inverse Property" ;
            ] .
        """
    g = Graph().parse(data=shape_ttl, format="turtle")
    focus_node_var = Var(value="focus_node")
    ns = NodeShape(
        uri=EX.AltInvPathShape,
        graph=g,
        kind="endpoint",
        focus_node=focus_node_var,
    )

    # Expected TSSP structure for ?focus_node ex:prop1|^ex:prop2 ?path_node_1 .
    expected_tssp = TriplesSameSubjectPath.from_spo(
        focus_node_var,
        PathAlternative.alt(
            IRI(value=EX.prop1),
            PathEltOrInverse(PathElt(PathPrimary(IRI(value=EX.prop2))), inverse=True),
        ),
        Var(value="path_node_1"),
    )

    alternative_inv_path_tssp = _alternative_path_tssp(ns)
    assert (
        alternative_inv_path_tssp is not None
    ), "Alternative path with inverse TSSP not found"
    # Same subject and same object
    assert alternative_inv_path_tssp.subject == expected_tssp.subject
    assert (
        alternative_inv_path_tssp.property_list_path.pairs[0][1]
        == expected_tssp.property_list_path.pairs[0][1]
    )

    # Check the alternative paths themselves (order insensitive)
    found_paths = alternative_inv_path_tssp.property_list_path.pairs[0][
        0
    ].sequence_paths
    expected_paths = expected_tssp.property_list_path.pairs[0][0].sequence_paths

    # Convert paths to a comparable representation (e.g., tuple of (IRI, inverse_flag))
    def get_path_repr(seq_path):
        elt_inv = seq_path.list_path_elt_or_inverse[0]
        return (elt_inv.path_elt.path_primary.value.value, elt_inv.inverse)

    found_reprs = {get_path_repr(p) for p in found_paths}
    expected_reprs = {get_path_repr(p) for p in expected_paths}

    assert (
        found_reprs == expected_reprs
    ), "Generated alternative paths (with inverse) do not match expected"
