from pathlib import Path

from rdflib import RDFS, URIRef, Graph
from sparql_grammar_pydantic import Var

from prez.services.query_generation.search_fuseki_fts import SearchQueryFusekiFTS
from prez.services.query_generation.shacl import PropertyShape


def test_query_gen():
    query_obj = SearchQueryFusekiFTS(term="test", limit=10, offset=0, predicates=[RDFS.label, RDFS.comment])
    query_string = query_obj.to_string()
    print(query_string)

def test_combo_query_gen():
    file = Path(__file__).parent.parent / "test_data" / "fts_property_shapes.ttl"
    ps_g = Graph().parse(file)
    ps1 = PropertyShape(
        uri=URIRef("FTSInverseSequenceShape"),
        graph=ps_g,
        kind="fts",  # "profile" would expand these out to plain triple pattern matches
        focus_node=Var(value="focus_node"),
        shape_number=100
    )
    ps2 = PropertyShape(
        uri=URIRef("FTSInverseSequenceShape"),
    )
    query = SearchQueryFusekiFTS(
        term="test",
        limit=10,
        offset=0,
        predicates=[RDFS.label, RDFS.comment],
        gpnt_list=gpnt_list
    )
    print('')
