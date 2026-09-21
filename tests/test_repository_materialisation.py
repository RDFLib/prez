"""How query results become a graph, and what that means for blank nodes.

The repositories move CONSTRUCT results through N-Triples, which is what keeps the
per-triple work out of Python. A consequence worth stating in a test: blank node
labels are scoped to the document they arrive in, so a blank node in one query's
results is a different node from one in another query's results. Prez's rdflib path
has always behaved this way, and so has every deployment against a remote endpoint,
which bulk-loads the endpoint's N-Triples response.
"""

import pytest
from pyoxigraph import BlankNode, NamedNode, RdfFormat, Store

from prez.repositories import PyoxigraphRepo

GEOMETRY = "http://www.opengis.net/ont/geosparql#hasGeometry"
WKT = "http://www.opengis.net/ont/geosparql#asWKT"


@pytest.fixture
def repo() -> PyoxigraphRepo:
    store = Store()
    store.load(
        (
            f"<http://feature> <{GEOMETRY}> _:g .\n" f'_:g <{WKT}> "POINT(0 0)" .\n'
        ).encode(),
        RdfFormat.N_TRIPLES,
    )
    return PyoxigraphRepo(store)


@pytest.mark.asyncio
async def test_blank_node_structure_survives_within_one_query(repo):
    """The path through a blank node is intact when one query returns all of it."""
    store = await repo.rdf_query_to_oxigraph_store(
        f"""CONSTRUCT {{ ?f <{GEOMETRY}> ?g . ?g <{WKT}> ?wkt }}
            WHERE {{ ?f <{GEOMETRY}> ?g . ?g <{WKT}> ?wkt }}"""
    )
    geometries = list(
        store.quads_for_pattern(NamedNode("http://feature"), NamedNode(GEOMETRY), None)
    )
    assert len(geometries) == 1
    geometry = geometries[0].object
    assert isinstance(geometry, BlankNode)
    # the same blank node carries the geometry literal
    assert len(list(store.quads_for_pattern(geometry, NamedNode(WKT), None))) == 1


@pytest.mark.asyncio
async def test_blank_nodes_from_separate_queries_are_separate_nodes(repo):
    """Two queries into one store: each brings its own blank nodes.

    Documented rather than desirable - it is what a blank node label means, and what
    the rdflib and remote endpoint paths have always done. Prez asks for the whole
    path through a blank node in a single query for this reason.
    """
    store = Store()
    for predicate in (GEOMETRY, WKT):
        await repo.rdf_query_to_oxigraph_store(
            f"CONSTRUCT {{ ?s <{predicate}> ?o }} WHERE {{ ?s <{predicate}> ?o }}",
            into_store=store,
        )
    blank_nodes = {
        term
        for quad in store
        for term in (quad.subject, quad.object)
        if isinstance(term, BlankNode)
    }
    assert len(blank_nodes) == 2


@pytest.mark.asyncio
async def test_empty_results_leave_the_store_alone(repo):
    store = await repo.rdf_query_to_oxigraph_store(
        "CONSTRUCT { ?s <http://nothing> ?o } WHERE { ?s <http://nothing> ?o }"
    )
    assert len(store) == 0
