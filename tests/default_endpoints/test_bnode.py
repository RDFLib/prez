from pathlib import Path

import pytest
from rdflib import Graph, URIRef

from prez.bnode import get_bnode_depth




@pytest.mark.parametrize(
    "input_file, iri, expected_depth",
    [
        ("bnode_depth-1.ttl", "https://data.idnau.org/pid/democat", 1),
        ("bnode_depth-2.ttl", "https://data.idnau.org/pid/democat", 2),
        ("bnode_depth-4.ttl", "https://data.idnau.org/pid/democat", 4),
        ("bnode_depth-2-2.ttl", "https://draft.com/Australian-physiographic-units", 2),
    ],
)
def test_bnode_depth(input_file: str, iri: str, expected_depth: int) -> None:
    file = Path(__file__).parent.parent.parent / "test_data" / input_file

    graph = Graph()
    graph.parse(file)

    depth = get_bnode_depth(URIRef(iri), graph)
    assert depth == expected_depth
