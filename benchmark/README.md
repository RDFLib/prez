# Benchmarks

Two tools, for two jobs.

## `ratchet.py` - stops performance regressing

Counters that are exact and machine independent, so they can fail a pull request:

| counter | what it says |
|---|---|
| `nodes` | grammar nodes built for a query |
| `chars` | length of the rendered query |
| `queries` | SPARQL queries a request sends |
| `shapes_parsed` | SHACL node shapes parsed during a warm request |

`baseline.json` holds the recorded values, and
`tests/test_performance_ratchet.py` checks them on every run of the test suite.
`queries` and `shapes_parsed` may only fall; the rest must match exactly, because a
query that renders differently is a deliberate change and should be looked at.

```shell
python benchmark/ratchet.py            # print the counters and what moved
python benchmark/ratchet.py --update   # record them after an intended change
```

Re-recording is normal - it is how a change to the generated queries gets reviewed.
Say in the commit message what moved and why. What the ratchet is really there to
catch is the silent kind of regression: `shapes_parsed` going from 0 to 19 because a
cache stopped being hit, or `queries` rising because a request started asking per
item.

Timings are deliberately not ratcheted. A shared CI runner varies by more than the
regressions worth catching, so a timing gate would either be ignored or removed.

## `query_construction.py` - measures where the time goes

Wall-clock timings, for looking at a change by hand. Everything it measures goes
through prez's own entry points, so it runs unchanged against any version of the
code and two runs can be compared directly.

```shell
python benchmark/query_construction.py --label before          # on the old code
python benchmark/query_construction.py --label after           # on the new code
python benchmark/compare.py benchmark/results/{before,after}.json
```

Useful flags: `--only` to pick scenario groups (`values`, `link`, `linke2e`,
`listing`, `cql`, `e2e`), `--sizes` to change the sizes of the scaling scenarios
(the default reaches 100,000, which takes a couple of minutes on the whole set),
`--repeat` for the number of runs (the minimum and median are reported), and
`--dump-queries DIR` to write out every query it renders, which is how two versions
are checked for generating equivalent SPARQL.

A scenario that raises is recorded as a failure and the run carries on, because at
the large sizes that is a result in itself: the previous library hit a recursion
limit past a certain query size.

The scenarios follow the phases of a request:

* **`values`** - the queries that take a `VALUES` clause per result: annotations and
  class lookups. Run at 100, 1,000, 5,000, 10,000, 50,000 and 100,000 terms, since
  they scale with the size of the response and clients do list at the large end. A
  100,000-row `VALUES` clause is a 3.3 MB query; prez builds one query rather than
  chunking, so that is what goes to the database.
* **`link`** / **`linke2e`** - link generation: the components query for a set of
  focus nodes, then the whole phase (class lookup, node shapes, query, link strings)
  cold and warm.
* **`listing`** - a listing request's pre-query work: the endpoint and profile node
  shapes, the CONSTRUCT query, and the count query.
* **`cql`** - a CQL `in` filter, at the same sizes, plus the default search query.
* **`e2e`** - whole requests through the app against an in-memory store loaded with
  `test_data`, cold (link and class caches cleared) and warm. No network hop, so
  these are the CPU cost of a request end to end.

`results/before.json` is the last measurement of the code before
sparql-grammar replaced sparql-grammar-pydantic, `results/after-port.json` the
same code with the swap and nothing else, and `results/after.json` the current
state; `compare.py` prints any two of them side by side. `results/before-large.json`
and `results/after-large.json` are the same pair over the scaling scenarios only,
out to 100,000 rows.

`quads_vs_stores.py` is unrelated to both: it compares ways of getting query results
into pyoxigraph, and needs a real endpoint to run against.
