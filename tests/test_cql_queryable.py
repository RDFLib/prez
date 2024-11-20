from pathlib import Path

from rdflib import Graph, URIRef
from sparql_grammar_pydantic import Var

from prez.services.query_generation.shacl import PropertyShape

test_file_1 = Path(__file__).parent.parent / "test_data/cql_queryable_shapes.ttl"
test_file_2 = Path(__file__).parent.parent / "test_data/cql_queryable_shapes_bdr.ttl"
data = Graph().parse(test_file_1, format="turtle")
data.parse(test_file_2, format="turtle")


def test_ps_1():
    ps = PropertyShape(
        uri=URIRef("http://example.com/SpeciesQueryableShape"),
        graph=data,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
    )
    assert (
        ps.tssp_list[0].to_string()
        == "?focus_node ^<http://example.com/hasFeatureOfInterest>/^<http://example.com/hasMember>*/<http://example.com/hasSimpleResult> ?path_node_3"
    )


def test_ps_2():
    ps = PropertyShape(
        uri=URIRef("http://example.com/BDRScientificNameQueryableShape"),
        graph=data,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
    )
    assert (
        ps.tssp_list[0].to_string()
        == "?focus_node ^<http://www.w3.org/ns/sosa/hasFeatureOfInterest>/<http://www.w3.org/ns/sosa/hasMember>/<http://www.w3.org/ns/sosa/hasResult>/<http://rs.tdwg.org/dwc/terms/scientificNameID> ?path_node_4"
    )
