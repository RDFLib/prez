"""Every Jena Lucene query prez emits must be syntactically valid SPARQL.

The Lucene index is called through a triple whose subject and object are RDF
collections::

    ( ?hit ?focus_node ?weight ?totalHits ) luc:query ( "default" "ore" 20 0 )

That is ordinary SPARQL syntax, which Jena gives a special meaning. prez used to
render it by hand and substitute the text into the finished query, because the
previous grammar library ran a collection's items together without separators
and turned a limit of ``20 0`` into ``200``. The substitution outlived the bug it
worked around and then broke the query itself: the replacement text carried its
own ``.``, the renderer had already written one after the block, and every query
on this path went out with ``. .`` in it.

So these tests parse what prez would send, rather than checking fragments of it.
A fragment assertion cannot see a doubled dot; a parser can.
"""

import re

import pyoxigraph
import pytest

from prez.services.query_generation.search_jena_lucene import SearchQueryJenaLucene
from prez.services.query_generation.umbrella import PrezQueryConstructor

#: The shapes a Lucene search takes, by the arguments that change the query.
VARIANTS = {
    "plain": {},
    "paged": {"limit": 5, "offset": 10},
    "pagination_pushed_down": {
        "limit": 5,
        "offset": 10,
        "pagination_pushed_down": True,
    },
    "no_matches": {"include_matches": False},
    "wildcard_term": {"term": None},
    "explicit_fields": {"search_fields": ["urn:jena:lucene:field#id"]},
    "filtered": {
        "filter_json": {"op": "=", "args": [{"property": "status"}, "active"]}
    },
    "sorted": {"order_by": "label", "order_by_direction": "ASC"},
    "faceted": {"facets": ["type", "status"]},
    "faceted_filtered_sorted": {
        "facets": ["type"],
        "filter_json": {"op": "=", "args": [{"property": "status"}, "active"]},
        "order_by": "label",
        "order_by_direction": "DESC",
    },
}


def build_search_query(**overrides) -> SearchQueryJenaLucene:
    kwargs = {
        "term": "ore",
        "limit": 20,
        "offset": 0,
        "lucene_index_name": "default",
        **overrides,
    }
    search_query = SearchQueryJenaLucene(**kwargs)
    # the class builds its parts lazily, and a listing reads all three
    search_query.inner_select_gpnt
    search_query.tss_list
    search_query.inner_select_vars
    return search_query


def emitted_query(search_query: SearchQueryJenaLucene) -> str:
    """The query string a listing request would send for this search."""
    if search_query.has_facets:
        return search_query.build_combined_query(
            construct_tss_list=list(search_query.tss_list)
            + list(search_query.facet_tss_list),
            profile_triples=[],
            profile_gpnt=[],
        ).to_string()
    return PrezQueryConstructor(
        construct_tss_list=list(search_query.tss_list),
        inner_select_vars=list(search_query.inner_select_vars),
        inner_select_gpnt=[search_query.inner_select_gpnt],
        limit=search_query.limit,
        offset=search_query.offset,
        order_by_value=search_query.order_by_val,
        order_by_direction=search_query.order_by_direction,
    ).to_string()


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_emitted_lucene_query_is_valid_sparql(name):
    query = emitted_query(build_search_query(**VARIANTS[name]))
    # an empty store is enough: this is asking the parser, not the data
    pyoxigraph.Store().query(query)


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_emitted_lucene_query_has_no_doubled_statement_separator(name):
    """The failure this file exists for, named so a regression reads plainly."""
    query = emitted_query(build_search_query(**VARIANTS[name]))
    assert " . ." not in re.sub(r"\s+", " ", query)


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_emitted_lucene_query_calls_the_index(name):
    """A query that parses but has lost the Lucene call would be no use."""
    query = emitted_query(build_search_query(**VARIANTS[name]))
    assert "urn:jena:lucene:index#query" in query
