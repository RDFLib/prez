from pathlib import Path

import pytest
from rdflib import Graph, URIRef, Namespace, Literal, BNode
from rdflib.namespace import SH, RDF, RDFS
from sparql_grammar_pydantic import (
    Var,
    IRI,
    TriplesSameSubjectPath,
    PropertyListPathNotEmpty,
    VerbPath,
    SG_Path,
    PathAlternative,
    PathSequence,
    PathEltOrInverse,
    PathElt,
    PathPrimary,
    ObjectListPath,
    ObjectPath,
    GraphNodePath,
    VarOrTerm,
    GraphTerm,
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
    expected_tssp = TriplesSameSubjectPath(
        content=(
            VarOrTerm(varorterm=focus_node_var),
            PropertyListPathNotEmpty(
                first_pair=(
                    VerbPath(
                        path=SG_Path(
                            path_alternative=PathAlternative(
                                sequence_paths=[
                                    PathSequence(
                                        list_path_elt_or_inverse=[
                                            PathEltOrInverse(
                                                path_elt=PathElt(
                                                    path_primary=PathPrimary(
                                                        value=IRI(value=EX.prop1)
                                                    ),
                                                    path_mod=None,
                                                ),
                                                inverse=False,
                                            )
                                        ]
                                    ),
                                    PathSequence(
                                        list_path_elt_or_inverse=[
                                            PathEltOrInverse(
                                                path_elt=PathElt(
                                                    path_primary=PathPrimary(
                                                        value=IRI(value=EX.prop2)
                                                    ),
                                                    path_mod=None,
                                                ),
                                                inverse=False,
                                            )
                                        ]
                                    ),
                                ]
                            )
                        )
                    ),
                    ObjectListPath(
                        object_paths=[
                            ObjectPath(
                                graph_node_path=GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=Var(value="path_node_1")
                                    )
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )

    # Find the TSSP generated for the alternative path property shape
    # Note: The NodeShape also generates a TSSP for the sh:targetClass (rdf:type)
    alternative_path_tssp = None
    for tssp in ns.tssp_list:
        # Check if the verb part matches the structure of an alternative path
        if (
            isinstance(tssp.content[1], PropertyListPathNotEmpty)
            and isinstance(tssp.content[1].first_pair[0], VerbPath)
            and isinstance(
                tssp.content[1].first_pair[0].path.path_alternative, PathAlternative
            )
            and len(tssp.content[1].first_pair[0].path.path_alternative.sequence_paths)
            == 2  # Check for two alternatives
        ):
            alternative_path_tssp = tssp
            break

    assert (
        alternative_path_tssp is not None
    ), "Alternative path TSSP not found in NodeShape tssp_list"
    assert (
        alternative_path_tssp == expected_tssp
    ), "Generated TSSP for alternative path does not match expected structure"


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
    expected_tssp = TriplesSameSubjectPath(
        content=(
            VarOrTerm(varorterm=focus_node_var),
            PropertyListPathNotEmpty(
                first_pair=(
                    VerbPath(
                        path=SG_Path(
                            path_alternative=PathAlternative(
                                sequence_paths=[
                                    # Sequence for ex:prop1
                                    PathSequence(
                                        list_path_elt_or_inverse=[
                                            PathEltOrInverse(
                                                path_elt=PathElt(
                                                    path_primary=PathPrimary(
                                                        value=IRI(value=EX.prop1)
                                                    ),
                                                    path_mod=None,
                                                ),
                                                inverse=False,
                                            )
                                        ]
                                    ),
                                    # Sequence for ^ex:prop2
                                    PathSequence(
                                        list_path_elt_or_inverse=[
                                            PathEltOrInverse(
                                                path_elt=PathElt(
                                                    path_primary=PathPrimary(
                                                        value=IRI(value=EX.prop2)
                                                    ),
                                                    path_mod=None,
                                                ),
                                                inverse=True,  # Inverse path flag
                                            )
                                        ]
                                    ),
                                ]
                            )
                        )
                    ),
                    ObjectListPath(
                        object_paths=[
                            ObjectPath(
                                graph_node_path=GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=Var(value="path_node_1")
                                    )
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )

    # Find the TSSP generated for the alternative path property shape
    alternative_inv_path_tssp = None
    for tssp in ns.tssp_list:
        if (
            isinstance(tssp.content[1], PropertyListPathNotEmpty)
            and isinstance(tssp.content[1].first_pair[0], VerbPath)
            and isinstance(
                tssp.content[1].first_pair[0].path.path_alternative, PathAlternative
            )
            and len(tssp.content[1].first_pair[0].path.path_alternative.sequence_paths)
            == 2
        ):
            # Further check if one path is inverse and the other is not
            seq1 = tssp.content[1].first_pair[0].path.path_alternative.sequence_paths[0]
            seq2 = tssp.content[1].first_pair[0].path.path_alternative.sequence_paths[1]
            if (
                len(seq1.list_path_elt_or_inverse) == 1
                and len(seq2.list_path_elt_or_inverse) == 1
            ):
                path1_inverse = seq1.list_path_elt_or_inverse[0].inverse
                path2_inverse = seq2.list_path_elt_or_inverse[0].inverse
                # Check if one is inverse and the other is not (order might vary)
                if path1_inverse != path2_inverse:
                    alternative_inv_path_tssp = tssp
                    break

    assert (
        alternative_inv_path_tssp is not None
    ), "Alternative path with inverse TSSP not found"
    # We need to compare content carefully as the order of alternatives might not be guaranteed
    # Check the structure and properties of the found TSSP against the expected one
    assert (
        alternative_inv_path_tssp.content[0] == expected_tssp.content[0]
    )  # Same subject
    assert isinstance(
        alternative_inv_path_tssp.content[1].first_pair[1], ObjectListPath
    )  # Same object structure
    assert (
        alternative_inv_path_tssp.content[1].first_pair[1]
        == expected_tssp.content[1].first_pair[1]
    )  # Same object variable

    # Check the alternative paths themselves (order insensitive)
    found_paths = (
        alternative_inv_path_tssp.content[1]
        .first_pair[0]
        .path.path_alternative.sequence_paths
    )
    expected_paths = (
        expected_tssp.content[1].first_pair[0].path.path_alternative.sequence_paths
    )

    # Convert paths to a comparable representation (e.g., tuple of (IRI, inverse_flag))
    def get_path_repr(seq_path):
        elt_inv = seq_path.list_path_elt_or_inverse[0]
        return (elt_inv.path_elt.path_primary.value.value, elt_inv.inverse)

    found_reprs = {get_path_repr(p) for p in found_paths}
    expected_reprs = {get_path_repr(p) for p in expected_paths}

    assert (
        found_reprs == expected_reprs
    ), "Generated alternative paths (with inverse) do not match expected"
