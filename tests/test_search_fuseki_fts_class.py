from pathlib import Path

from rdflib import RDFS, URIRef, Graph
from sparql_grammar_pydantic import Var, GroupGraphPattern, GroupGraphPatternSub, TriplesBlock, GroupOrUnionGraphPattern

from prez.services.query_generation.search_fuseki_fts import SearchQueryFusekiFTS
from prez.services.query_generation.shacl import PropertyShape


def test_query_gen():
    query_obj = SearchQueryFusekiFTS(term="test", limit=10, offset=0, predicates=[RDFS.label, RDFS.comment])
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
        shape_number=100
    )
    ps2 = PropertyShape(
        uri=URIRef("http://example.com/FTSSequenceShape"),
        graph=ps_g,
        kind="fts",  # "profile" would expand these out to plain triple pattern matches
        focus_node=Var(value="focus_node"),
        shape_number=101
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
