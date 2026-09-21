"""Deterministic performance counters, and the baseline they are held to.

Timings cannot gate a pull request: a shared CI runner varies by more than the
regressions worth catching. These counters can. They are exact, machine independent
and cheap, and they move only when the code changes:

* ``nodes`` - grammar nodes built for a query. Rises when construction starts
  building structure it does not need.
* ``chars`` - length of the rendered query. Rises when the query itself grows.
* ``queries`` - SPARQL queries a request sends. Rises when a request stops reusing
  a result, or starts asking per item.
* ``shapes_parsed`` - SHACL node shapes parsed during a request. Rises when the
  shape cache stops being hit, which is the regression that would quietly undo
  most of the request-path work.

Run ``python benchmark/ratchet.py`` to print the current counters against the
baseline, and ``python benchmark/ratchet.py --update`` to record them after a
deliberate change. ``tests/test_performance_ratchet.py`` checks them on every run
of the test suite; ``benchmark/query_construction.py`` is the timing benchmark,
for looking at a change by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SPARQL_REPO_TYPE", "pyoxigraph_memory")
os.environ.setdefault("ENABLE_SPARQL_ENDPOINT", "true")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

#: Counters that must not rise. Anything else in the baseline must match exactly:
#: a query that renders differently is a deliberate change, and re-recording the
#: baseline is how it gets reviewed.
UPPER_BOUND_KEYS = frozenset({"queries", "shapes_parsed"})


# ---------------------------------------------------------------------------
# query construction counters
# ---------------------------------------------------------------------------


def _count_nodes(node) -> int:
    return sum(1 for _ in node.walk())


def construction_counters() -> dict[str, dict[str, int]]:
    """Tree size and rendered length for one query of each kind prez builds."""
    from sparql_grammar import IRI, Var

    from prez.models.query_params import ListingQueryParams
    from prez.services.query_generation.annotations import AnnotationsConstructQuery
    from prez.services.query_generation.classes import ClassesSelectQuery
    from prez.services.query_generation.count import CountQuery
    from prez.services.query_generation.cql import CQLParser
    from prez.services.query_generation.search_default import SearchQueryRegex
    from prez.services.query_generation.umbrella import (
        PrezQueryConstructor,
        merge_listing_query_grammar_inputs,
    )

    counters: dict[str, dict[str, int]] = {}

    def record(name, query, text=None):
        counters[name] = {
            "nodes": _count_nodes(query),
            "chars": len(text or query.to_string()),
        }

    terms = [IRI(value=f"https://example.com/term/{i}") for i in range(100)]
    record("annotations_100", AnnotationsConstructQuery(terms=terms))
    record("classes_100", ClassesSelectQuery(iris=terms))

    cql = {
        "op": "and",
        "args": [
            {
                "op": "in",
                "args": [
                    {"property": "https://example.com/p"},
                    [f"https://example.com/v/{i}" for i in range(100)],
                ],
            },
            {"op": "=", "args": [{"property": "https://example.com/q"}, "x"]},
        ],
    }
    parser = CQLParser(cql_json=cql)
    parser.parse()
    record("cql_in_100", parser.query_object, parser.query_str)

    search = SearchQueryRegex(term="test", limit=10, offset=0)
    record("search", search)

    query_params = ListingQueryParams(
        limit=20,
        page=1,
        _filter=None,
        bbox=[],
        datetime=None,
        order_by=None,
        order_by_direction=None,
    )
    kwargs = merge_listing_query_grammar_inputs(query_params=query_params)
    listing = PrezQueryConstructor(**kwargs)
    record("listing", listing)
    record("listing_count", CountQuery(original_subselect=listing.inner_select))
    record(
        "object",
        PrezQueryConstructor(
            construct_tss_list=None,
            profile_triples=[],
            profile_gpnt=[],
        ),
    )
    return counters


# ---------------------------------------------------------------------------
# request counters
# ---------------------------------------------------------------------------

#: The requests to count, and how deep in the hierarchy they sit. Chosen for
#: coverage of the code paths, not for breadth: a listing, an object, a listing of
#: concepts (the page that generates the most links), and a search.
REQUEST_SCENARIOS = {
    "catalogs": "/catalogs?limit=20",
    "catalog_object": "/catalogs/exm:CatalogOne",
    "collections": "/catalogs/exm:CatalogOne/collections?limit=20",
    "search": "/search?q=the&limit=20",
}


class _Counters:
    def __init__(self):
        self.queries = 0
        self.shapes_parsed = 0

    def reset(self):
        self.queries = 0
        self.shapes_parsed = 0


def request_counters() -> dict[str, dict[str, int]]:
    """Queries sent and node shapes parsed, per request, with caches warm.

    Warm, because a deployment serving the same endpoints repeatedly is warm, and
    because the cold numbers depend on what a previous scenario happened to load.
    """
    from fastapi.testclient import TestClient
    from pyoxigraph import RdfFormat

    from prez.app import assemble_app
    from prez.cache import store
    from prez.repositories.base import Repo
    from prez.services.query_generation import shacl

    for file in (REPO_ROOT / "test_data").glob("**/*.ttl"):
        store.load(file.read_bytes(), RdfFormat.TURTLE)

    counters = _Counters()
    original_send = Repo.send_queries
    original_init = shacl.NodeShape.__init__

    async def counting_send(self, rdf_queries, tabular_queries=(), *args, **kwargs):
        counters.queries += len([q for q in rdf_queries if q]) + len(
            list(tabular_queries)
        )
        return await original_send(self, rdf_queries, tabular_queries, *args, **kwargs)

    def counting_init(self, **data):
        counters.shapes_parsed += 1
        original_init(self, **data)

    Repo.send_queries = counting_send
    shacl.NodeShape.__init__ = counting_init
    try:
        results = {}
        with TestClient(assemble_app()) as client:
            headers = {"Accept": "text/anot+turtle"}
            for name, url in REQUEST_SCENARIOS.items():
                for _ in range(2):  # warm the caches this request can fill
                    response = client.get(url, headers=headers)
                    assert response.status_code == 200, (url, response.status_code)
                counters.reset()
                client.get(url, headers=headers)
                results[name] = {
                    "queries": counters.queries,
                    "shapes_parsed": counters.shapes_parsed,
                }
        return results
    finally:
        Repo.send_queries = original_send
        shacl.NodeShape.__init__ = original_init


def measure() -> dict[str, dict[str, int]]:
    """Every counter, keyed by scenario."""
    measured = {f"query:{k}": v for k, v in construction_counters().items()}
    measured.update({f"request:{k}": v for k, v in request_counters().items()})
    return measured


def measure_in_subprocess() -> dict[str, dict[str, int]]:
    """The counters, measured in a fresh interpreter.

    Counting requests means loading test data into the store the app builds itself
    around, and emptying the annotation and class caches - module state that the
    rest of the test suite shares. In its own process it touches nothing else, and
    the counts do not depend on what ran before them.
    """
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "counters.json"
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--json", str(out)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0 or not out.exists():
            raise RuntimeError(
                f"measuring the counters failed:\n{result.stdout}\n{result.stderr}"
            )
        return json.loads(out.read_text())


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


def load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text())["counters"]


def compare(baseline: dict, measured: dict) -> list[str]:
    """The failures, as sentences. Empty when nothing regressed."""
    problems = []
    for scenario, expected in baseline.items():
        actual = measured.get(scenario)
        if actual is None:
            problems.append(f"{scenario}: no longer measured")
            continue
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if actual_value is None:
                problems.append(f"{scenario}.{key}: no longer measured")
            elif key in UPPER_BOUND_KEYS:
                if actual_value > expected_value:
                    problems.append(
                        f"{scenario}.{key}: {actual_value}, up from {expected_value}"
                    )
            elif actual_value != expected_value:
                direction = "up from" if actual_value > expected_value else "down from"
                problems.append(
                    f"{scenario}.{key}: {actual_value}, {direction} {expected_value}"
                )
    for scenario in measured:
        if scenario not in baseline:
            problems.append(f"{scenario}: not in the baseline")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--update", action="store_true", help="record the current counters"
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="write the counters to this file as JSON (the app itself logs to stdout)",
    )
    args = parser.parse_args()

    measured = measure()
    if args.json:
        Path(args.json).write_text(json.dumps(measured, indent=2) + "\n")
        return 0
    if args.update:
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "note": (
                        "Deterministic performance counters. Update with "
                        "`python benchmark/ratchet.py --update` when a change to the "
                        "generated queries or the request path is intended, and say why "
                        "in the commit message."
                    ),
                    "counters": measured,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"wrote {BASELINE_PATH}")
        return 0

    problems = compare(load_baseline(), measured)
    for scenario, values in measured.items():
        print(f"{scenario:34s} {json.dumps(values)}")
    if problems:
        print("\nregressed:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("\nno change against the baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
