from unittest.mock import patch

from pathlib import Path

from rdflib import RDFS, Graph, URIRef, DCTERMS, RDF
from sparql_grammar_pydantic import (
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    TriplesBlock,
    Var,
    TriplesSameSubjectPath,
    IRI,
)

from prez.enums import SearchMethod
from prez.services.query_generation.search_fuseki_fts import SearchQueryFusekiFTS
from prez.services.query_generation.shacl import PropertyShape


def test_query_gen():
    query_obj = SearchQueryFusekiFTS(
        term="test", limit=10, offset=0, non_shacl_predicates=[RDFS.label, RDFS.comment]
    )
    query_string = query_obj.to_string()
    print(query_string)


def test_combo_query_gen():
    """test can union the property shape inverse sequence paths etc."""
    file = Path(__file__).parent.parent / "test_data" / "fts_property_shapes.ttl"
    ps_g = Graph().parse(file)
    ps1 = PropertyShape(
        uri=URIRef("http://example.com/FTSInverseSequenceShape"),
        graph=ps_g,
        kind="fts",  # "profile" would expand these out to plain triple pattern matches
        focus_node=Var(value="focus_node"),
        shape_number=100,
    )
    ps2 = PropertyShape(
        uri=URIRef("http://example.com/FTSSequenceShape"),
        graph=ps_g,
        kind="fts",  # "profile" would expand these out to plain triple pattern matches
        focus_node=Var(value="focus_node"),
        shape_number=101,
    )
    tspp_lists = [ps1.tssp_list, ps2.tssp_list]

    ggp_list = []
    for inner_list in tspp_lists:
        ggp_list.append(
            GroupGraphPattern(
                content=GroupGraphPatternSub(
                    triples_block=TriplesBlock.from_tssp_list(inner_list)
                )
            )
        )
    gougp = GroupOrUnionGraphPattern(group_graph_patterns=ggp_list)
    assert gougp


def test_bnode_filter():
    tssp_list = [
        TriplesSameSubjectPath.from_spo(
            Var(value="focus_node"),
            IRI(value="http://example.com/hasFeatureOfInterest"),
            Var(value="path_node_1"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_1"),
            IRI(value="http://example.com/hasMember"),
            Var(value="path_node_2"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_2"),
            IRI(value="http://www.w3.org/2000/01/rdf-schema#label"),
            Var(value="fts_search_node"),
        ),
    ]
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        non_shacl_predicates=[RDFS.label, RDFS.comment],
        shacl_tssp_preds=[(tssp_list, [RDFS.label])],
    )
    query_string = query_obj.to_string()
    assert "FILTER (! isBLANK(?focus_node))" in query_string


def test_oomp():
    tssp_list = [
        TriplesSameSubjectPath.from_spo(
            Var(value="focus_node"),
            IRI(value=DCTERMS.hasPart),
            Var(value="path_node_1"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_1"),
            IRI(value=DCTERMS.hasPart),
            Var(value="path_node_2"),
        ),
        TriplesSameSubjectPath.from_spo(
            Var(value="path_node_2"),
            IRI(value=RDF.value),
            Var(value="fts_search_node"),
        ),
    ]
    query_obj = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        shacl_tssp_preds=[(tssp_list, [RDF.value])],
    )
    query_string = query_obj.to_string()
    assert "FILTER (! isBLANK(?focus_node))" in query_string


@patch("prez.dependencies.settings")
def test_one_or_more_path(mock_settings, client):
    mock_settings.search_method = SearchMethod.FTS_FUSEKI
    r = client.get("/search?q=test&predicates=oomp&_mediatype=application/sparql-query")
    assert r.status_code == 200
