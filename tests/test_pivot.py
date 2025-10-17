"""test_pivot.py

Tests to ensure that the pivot shacl extension works as expected
"""

from pathlib import Path

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, SDO, SOSA, XSD
from sparql_grammar_pydantic import Var

from prez.services.query_generation.shacl import NodeShape
from prez.services.query_generation.umbrella import PrezQueryConstructor

data = Path(__file__).parent.parent / "test_data" / "pivot.ttl"
profiles = Path(__file__).parent.parent / "test_data" / "pivot_profiles.ttl"

data_graph = Graph()
data_graph.parse(data)
profiles_graph = Graph()
profiles_graph.parse(profiles)

PROF = Namespace("https://prez.dev/profile/")
EX = Namespace("https://example.org/")


def test_pivot_path():
    """test processing of a simple path"""
    nodeshape = NodeShape(
        uri=PROF.pivotPath,
        graph=profiles_graph,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    query = PrezQueryConstructor(
        construct_tss_list=nodeshape.tss_list,
        profile_triples=nodeshape.tssp_list,
        profile_gpnt=nodeshape.gpnt_list,
    )
    results = data_graph.query(query.to_string())
    expected_triples = [
        (EX.catalog, EX.role1, Literal("agent 1")),
        (EX.catalog, EX.role2, Literal("agent 2")),
        (EX.catalog, EX.role3, Literal("agent 3")),
    ]
    assert all([triple in results.graph for triple in expected_triples])


def test_pivot_inverse_path():
    """test processing of an inverse path"""
    nodeshape = NodeShape(
        uri=PROF.pivotInversePath,
        graph=profiles_graph,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    query = PrezQueryConstructor(
        construct_tss_list=nodeshape.tss_list,
        profile_triples=nodeshape.tssp_list,
        profile_gpnt=nodeshape.gpnt_list,
    )
    results = data_graph.query(query.to_string())
    expected_triples = [
        (EX.sample1, EX.color, Literal("brown")),
        (EX.sample2, EX.color, Literal("red")),
    ]
    assert all([triple in results.graph for triple in expected_triples])


def test_pivot_sequence_path():
    """test processing of a sequence path"""
    nodeshape = NodeShape(
        uri=PROF.pivotSequencePath,
        graph=profiles_graph,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    query = PrezQueryConstructor(
        construct_tss_list=nodeshape.tss_list,
        profile_triples=nodeshape.tssp_list,
        profile_gpnt=nodeshape.gpnt_list,
    )
    results = data_graph.query(query.to_string())
    expected_triples = [
        (EX.drillhole, EX.earthworms, Literal(True)),
        (EX.drillhole, EX.earthworms, Literal(False)),
    ]
    assert all([triple in results.graph for triple in expected_triples])


def test_pivot_alternative_path():
    nodeshape = NodeShape(
        uri=PROF.pivotAlternativePath,
        graph=profiles_graph,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    query = PrezQueryConstructor(
        construct_tss_list=nodeshape.tss_list,
        profile_triples=nodeshape.tssp_list,
        profile_gpnt=nodeshape.gpnt_list,
    )
    results = data_graph.query(query.to_string())
    expected_triples = [
        (EX.otherCatalog, SDO.Apartment, Literal("under the bed")),
        (EX.otherCatalog, SDO.House, Literal("on the shelf")),
    ]
    assert all([triple in results.graph for triple in expected_triples])


def test_pivot_oneormore_path():
    nodeshape = NodeShape(
        uri=PROF.pivotOneOrMorePath,
        graph=profiles_graph,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    query = PrezQueryConstructor(
        construct_tss_list=nodeshape.tss_list,
        profile_triples=nodeshape.tssp_list,
        profile_gpnt=nodeshape.gpnt_list,
    )
    results = data_graph.query(query.to_string())
    expected_triples = [
        (EX.otherCatalog, EX.key1, Literal("value1")),
        (EX.otherCatalog, EX.key2, Literal("value2")),
        (EX.subResource1, EX.key2, Literal("value2")),
    ]
    assert all([triple in results.graph for triple in expected_triples])


def test_pivot_union():
    nodeshape = NodeShape(
        uri=PROF.pivotUnion,
        graph=profiles_graph,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    query = PrezQueryConstructor(
        construct_tss_list=nodeshape.tss_list,
        profile_triples=nodeshape.tssp_list,
        profile_gpnt=nodeshape.gpnt_list,
    )
    results = data_graph.query(query.to_string())
    expected_triples = [
        (EX.sample1, RDF.type, SOSA.Sample),
        (EX.sample1, SDO.identifier, Literal("abc123", datatype=XSD.token)),
        (EX.sample2, RDF.type, SOSA.Sample),
        (EX.sample2, EX.color, Literal("red")),
    ]
    assert all([triple in results.graph for triple in expected_triples])


def test_pivot_value_sequence():
    nodeshape = NodeShape(
        uri=PROF.pivotValueSequence,
        graph=profiles_graph,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    query = PrezQueryConstructor(
        construct_tss_list=nodeshape.tss_list,
        profile_triples=nodeshape.tssp_list,
        profile_gpnt=nodeshape.gpnt_list,
    )
    results = data_graph.query(query.to_string())
    expected_triples = [
        (EX.sample1, EX.color, Literal("brown")),
        (EX.sample1, EX.earthworms, Literal(False)),
    ]
    assert all([triple in results.graph for triple in expected_triples])
