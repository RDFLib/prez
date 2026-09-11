"""Two VALUES clauses joined against one triple pattern defeat the query planner.

Measured on pyoxigraph with a 21,010 quad store: the annotations CONSTRUCT over
2,000 terms took 1,227 ms in the two-VALUES form and 9 ms once the property list
became a UNION, for byte-identical results. One VALUES clause is fine - it matches a
hand-written index lookup - so these tests pin the rewrite rather than banning VALUES.
"""

import re

from pyoxigraph import (
    BlankNode,
    DefaultGraph,
    Literal,
    NamedNode,
    Quad,
    Store,
)
from sparql_grammar import IRI

from prez.services.query_generation.annotations import AnnotationsConstructQuery

LEGACY_TWO_VALUES = """
CONSTRUCT {{ ?term ?prezAnotProp ?annotation }}
WHERE {{
  VALUES ?term {{ {terms} }}
  VALUES (?prop ?prezAnotProp) {{ {props} }}
  ?term ?prop ?annotation
  FILTER (LANG(?annotation) IN ("en", "") || isURI(?annotation))
}}
"""


def build_store(n: int = 200) -> tuple[Store, list[NamedNode]]:
    """Terms annotated with each source predicate in turn, over a spread of object types."""
    store = Store()
    default = DefaultGraph()
    pairs = AnnotationsConstructQuery.get_prez_annotation_tuples()
    objects = [
        Literal("v", language="en"),  # the default language
        Literal("v", language="fr"),  # filtered out
        Literal("v"),  # no language tag - kept
        NamedNode("https://example.com/o"),  # isURI - kept
        BlankNode(),  # filtered out
    ]
    terms = []
    for i in range(n):
        term = NamedNode(f"https://example.com/t/{i}")
        terms.append(term)
        prop = NamedNode(str(pairs[i % len(pairs)][0]))
        store.add(Quad(term, prop, objects[i % len(objects)], default))
        # a predicate that is not an annotation predicate at all
        store.add(
            Quad(
                term, NamedNode("https://example.com/unrelated"), Literal("x"), default
            )
        )
    return store, terms


def triples(store: Store, query: str) -> set:
    return {(t[0], t[1], t[2]) for t in store.query(query)}


def test_annotations_query_matches_the_two_values_form():
    store, terms = build_store()
    legacy = LEGACY_TWO_VALUES.format(
        terms=" ".join(f"<{t.value}>" for t in terms),
        props=" ".join(
            f"(<{p}> <{pz}>)"
            for p, pz in AnnotationsConstructQuery.get_prez_annotation_tuples()
        ),
    )
    current = AnnotationsConstructQuery(
        terms=[IRI(value=t.value) for t in terms]
    ).to_string()
    by_legacy = triples(store, legacy)
    assert by_legacy  # the comparison would be vacuous if both were empty
    assert triples(store, current) == by_legacy


def test_annotations_query_has_one_values_clause():
    query = AnnotationsConstructQuery(
        terms=[IRI(value="https://example.com/a")]
    ).to_string()
    assert len(re.findall(r"\bVALUES\b", query)) == 1
