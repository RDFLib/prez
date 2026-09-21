"""The performance counters must not regress.

These are exact counts, not timings: the number of grammar nodes a query is built
from, the length of the rendered query, and the number of SPARQL queries and SHACL
node shape parses a request costs. They do not vary with the machine, so they can
fail a pull request, where a timing cannot.

A failure is not necessarily a bug. Changing the generated queries changes these
numbers, and the fix is to look at the difference, decide it is what was intended,
and re-record the baseline:

    python benchmark/ratchet.py            # show the counters and what moved
    python benchmark/ratchet.py --update   # record them, and say why in the commit

See benchmark/README.md.
"""

import pytest

from benchmark.ratchet import compare, load_baseline, measure


@pytest.fixture(scope="module")
def counters():
    return measure()


def test_no_counter_regressed(counters):
    problems = compare(load_baseline(), counters)
    assert not problems, "performance counters moved:\n  " + "\n  ".join(problems)


def test_warm_requests_reuse_parsed_node_shapes(counters):
    """A warm request parses no node shapes at all.

    Spelled out separately from the baseline because it is the property the shape
    cache exists for, and the one whose loss would be least visible.
    """
    parsed = {
        name: values["shapes_parsed"]
        for name, values in counters.items()
        if name.startswith("request:")
    }
    assert parsed, "no request scenarios were measured"
    assert all(count == 0 for count in parsed.values()), parsed
