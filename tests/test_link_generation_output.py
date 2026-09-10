"""Link generation must emit the links themselves, not just the counters.

The performance work batched link writes, and in splitting the old
``add_links_to_graph_and_cache`` into the pure ``link_quads`` the append that
writes ``prez:members`` was dropped along with the guard in front of it. Every
response lost its members links, and the ratchet did not notice, because it
counts queries and node shapes rather than what comes back. So these tests
assert on the triples.
"""

from collections import Counter

import pytest
from pyoxigraph import NamedNode as OxiNamedNode
from rdflib import Graph, URIRef

from prez.reference_data.prez_ns import PREZ
from prez.services.link_generation import link_quads


def predicate_counts(response) -> Counter:
    graph = Graph().parse(data=response.text, format="turtle")
    return Counter(str(p) for p in graph.predicates())


def test_listing_response_carries_members_links(client):
    """A catalogue listing links to each catalogue's collections."""
    counts = predicate_counts(
        client.get("/catalogs?limit=20", headers={"accept": "text/anot+turtle"})
    )
    assert counts[str(PREZ.members)] > 0, "no prez:members links in the response"
    assert counts[str(PREZ.link)] > 0
    assert counts[str(PREZ.identifier)] > 0


def test_nested_listing_response_carries_members_links(client):
    counts = predicate_counts(
        client.get(
            "/catalogs/exm:CatalogOne/collections?limit=20",
            headers={"accept": "text/anot+turtle"},
        )
    )
    assert counts[str(PREZ.members)] > 0, "no prez:members links in the response"


def test_link_quads_emits_the_members_link():
    quads = link_quads(
        members_link="/catalogs/exm:cat/collections",
        object_link="/catalogs/exm:cat",
        uri_node=OxiNamedNode("https://example.com/cat"),
        identifiers={URIRef("https://example.com/cat"): "exm:cat"},
    )
    members = [q for q in quads if q.predicate.value == str(PREZ.members)]
    assert len(members) == 1
    assert members[0].object.value == "/catalogs/exm:cat/collections"


def test_link_quads_keeps_only_the_first_members_link_per_object():
    """Several node shapes can deliver one class; the first members link wins.

    The run of links reaches the cache in one write at the end, so the set is
    what sees the earlier link - the cache cannot.
    """
    uri_node = OxiNamedNode("https://example.com/cat")
    seen: set = set()
    first = link_quads("/first", "/catalogs/exm:cat", uri_node, {}, seen)
    second = link_quads("/second", "/catalogs/exm:cat", uri_node, {}, seen)
    assert [
        q.object.value for q in first if q.predicate.value == str(PREZ.members)
    ] == ["/first"]
    assert [q for q in second if q.predicate.value == str(PREZ.members)] == []


def test_link_quads_without_a_members_link_emits_none():
    quads = link_quads(
        None, "/catalogs/exm:cat", OxiNamedNode("https://example.com/cat"), {}
    )
    assert not [q for q in quads if q.predicate.value == str(PREZ.members)]
