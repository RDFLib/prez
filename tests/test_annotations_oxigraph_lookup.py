"""The pyoxigraph index-lookup path must return what AnnotationsConstructQuery returns."""

from pyoxigraph import (
    BlankNode,
    DefaultGraph,
    Literal,
    NamedNode,
    NamedNode as OxiNamedNode,
    Quad,
    QueryTriples,
    Store,
)
from rdflib import RDF, RDFS, SDO, SKOS
from rdflib.namespace import DCTERMS
from sparql_grammar import IRI

from prez.reference_data.prez_ns import PREZ
from prez.services.annotations import _lookup_annotations
from prez.services.query_generation.annotations import AnnotationsConstructQuery


def nn(term) -> NamedNode:
    return NamedNode(str(term))


def build_store() -> tuple[Store, list[OxiNamedNode]]:
    """A store exercising each branch of the FILTER, plus terms with no annotations at all."""
    store = Store()
    default = DefaultGraph()
    a, b, c = (
        nn("https://example.com/a"),
        nn("https://example.com/b"),
        nn("https://example.com/c"),
    )
    quads = [
        # the language filter
        Quad(a, nn(SKOS.prefLabel), Literal("A", language="en"), default),
        Quad(a, nn(RDFS.label), Literal("A-fr", language="fr"), default),
        Quad(a, nn(DCTERMS.title), Literal("A-plain"), default),
        # isURI(?annotation) - a URI object passes regardless of language
        Quad(a, nn(SDO.color), nn("https://example.com/red"), default),
        # a blank node object fails both sides of the filter
        Quad(a, nn(DCTERMS.description), BlankNode(), default),
        # more than one source predicate mapping to the same prez predicate
        Quad(b, nn(SKOS.definition), Literal("B def", language="en"), default),
        Quad(b, nn(DCTERMS.description), Literal("B desc"), default),
        Quad(b, nn(DCTERMS.provenance), Literal("B prov"), default),
        Quad(b, nn(RDF.value), Literal("B value"), default),
        # a predicate that is not an annotation predicate
        Quad(b, nn("https://example.com/unrelated"), Literal("ignored"), default),
        # a named graph - invisible to a query without use_default_graph_as_union
        Quad(
            c,
            nn(SKOS.prefLabel),
            Literal("C", language="en"),
            nn("https://example.com/g"),
        ),
    ]
    for quad in quads:
        store.add(quad)
    # d has nothing at all
    terms = [a, b, c, nn("https://example.com/d")]
    return store, terms


def triples_from_query(store: Store, terms: list[OxiNamedNode]) -> set:
    query = AnnotationsConstructQuery(
        terms=[IRI(value=term.value) for term in terms]
    ).to_string()
    results: QueryTriples = store.query(query)
    return {(t[0], t[1], t[2]) for t in results}


def test_lookup_matches_construct_query():
    store, terms = build_store()
    by_query = triples_from_query(store, terms)
    by_lookup = {(q[0], q[1], q[2]) for q in _lookup_annotations(store, terms)}
    assert by_lookup == by_query
    assert by_lookup  # the comparison would be vacuous if both were empty


def test_lookup_maps_predicates():
    store, terms = build_store()
    by_lookup = {(q[0], q[1], q[2]) for q in _lookup_annotations(store, terms)}
    a = nn("https://example.com/a")
    b = nn("https://example.com/b")
    assert (a, nn(PREZ.label), Literal("A", language="en")) in by_lookup
    assert (a, nn(PREZ.label), Literal("A-plain")) in by_lookup
    assert (b, nn(PREZ.description), Literal("B desc")) in by_lookup
    assert (b, nn(PREZ.value), Literal("B value")) in by_lookup
    # other_predicates keep their own predicate rather than getting a prez: one
    assert (a, nn(SDO.color), nn("https://example.com/red")) in by_lookup
    # filtered out: another language, a blank node object, a named graph, a term with no data
    assert not [t for t in by_lookup if t[2] == Literal("A-fr", language="fr")]
    assert not [t for t in by_lookup if t[0] == nn("https://example.com/c")]
    assert not [t for t in by_lookup if t[1] == nn("https://example.com/unrelated")]
