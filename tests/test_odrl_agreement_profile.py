from pathlib import Path

from pyoxigraph import DefaultGraph, Quad, RdfFormat, Store
from rdflib import Graph, Namespace, RDF, URIRef
from sparql_grammar_pydantic import IRI

from prez.services.query_generation.shacl import NodeShape


ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
SCHEMA = Namespace("https://schema.org/")
PROFILE = URIRef("https://prez.dev/profile/odrl-agreement")
AGREEMENT = URIRef("https://data.idnau.org/pid/policy/telstra-ngaanyatjarra-ilua")
PERMISSION_ACCESS = URIRef(
    "https://data.idnau.org/pid/policy/telstra-ngaanyatjarra-ilua-permission-access"
)
PERMISSION_READ = URIRef(
    "https://data.idnau.org/pid/policy/telstra-ngaanyatjarra-ilua-permission-read-summary"
)
TARGET = URIRef("https://data.idnau.org/pid/nntt/WI2004-006")


def _profile_shape() -> NodeShape:
    profile_path = Path(__file__).parents[1] / "examples/profiles/odrl_agreement.ttl"
    profile_graph = Graph().parse(profile_path)
    return NodeShape(
        uri=PROFILE,
        graph=profile_graph,
        kind="profile",
        focus_node=IRI(value=AGREEMENT),
    )


def _construct_query(shape: NodeShape) -> str:
    """Render this isolated spike without importing the whole FastAPI service."""
    construct = " .\n".join(triple.to_string() for triple in shape.tss_list) + " ."
    where = "\n".join(triple.to_string() for triple in shape.tssp_list)
    where += "\n" + "\n".join(pattern.to_string() for pattern in shape.gpnt_list)
    return f"CONSTRUCT {{\n{construct}\n}} WHERE {{\n{where}\n}}"


def _fixture_as_union_default_graph() -> Store:
    source = Store()
    source.load(
        (Path(__file__).parent / "fixtures/odrl_agreement.trig").read_bytes(),
        RdfFormat.TRIG,
    )
    union = Store()
    default = DefaultGraph()
    for quad in source:
        union.add(Quad(quad.subject, quad.predicate, quad.object, default))
    return union


def test_profile_constructs_named_permission_subgraphs_without_aliases():
    query = _construct_query(_profile_shape())

    assert f"<{AGREEMENT}> <{ODRL.permission}>" in query
    assert f"<{ODRL.action}>" in query
    assert f"<{ODRL.assigner}>" in query
    assert f"<{ODRL.assignee}>" in query
    assert f"<{ODRL.target}>" in query
    assert "pathAlias" not in query


def test_two_permissions_remain_grouped_in_the_api_rdf():
    store = _fixture_as_union_default_graph()
    shape = _profile_shape()
    query = _construct_query(shape)

    result = Graph().parse(
        data=store.query(query).serialize(format=RdfFormat.N_TRIPLES), format="nt"
    )

    assert set(result.objects(AGREEMENT, ODRL.permission)) == {
        PERMISSION_ACCESS,
        PERMISSION_READ,
    }
    assert (PERMISSION_ACCESS, ODRL.action, ODRL.use) in result
    assert (PERMISSION_ACCESS, ODRL.target, TARGET) in result
    assert (PERMISSION_READ, ODRL.action, ODRL.read) in result
    assert (
        PERMISSION_READ,
        ODRL.target,
        URIRef(
            "https://data.idnau.org/pid/resource/dd9b004b-1c22-5b53-8381-bd93760ee922"
        ),
    ) in result
    assert (PERMISSION_ACCESS, RDF.type, ODRL.Permission) in result
    assert (TARGET, SCHEMA.name, None) not in result


def test_target_in_a_separate_named_graph_requires_graph_aware_lookup():
    fixture = Path(__file__).parent / "fixtures/odrl_agreement.trig"
    store = Store()
    store.load(fixture.read_bytes(), RdfFormat.TRIG)
    default_graph_labels = list(
        store.query(f"SELECT ?label WHERE {{ <{TARGET}> <{SCHEMA.name}> ?label }}")
    )
    named_graph_labels = list(
        store.query(
            f"SELECT ?label WHERE {{ GRAPH <{TARGET}> {{ <{TARGET}> <{SCHEMA.name}> ?label }} }}"
        )
    )

    assert default_graph_labels == []
    assert (
        named_graph_labels[0][0].value == "Telstra Ngaanyatjarra ILUA registered area"
    )
