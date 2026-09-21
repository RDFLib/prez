# Jena Lucene Pagination Notes

**Date**: 2026-04-14

## Current Direction

For the Jena Lucene JSON code path, Prez now treats pagination as a configurable pushdown concern:

- `fts_limit` is the Lucene hit cap when set
- `lucene_limit_offset_pushdown` controls whether Prez omits the outer SPARQL `LIMIT/OFFSET`

When `lucene_limit_offset_pushdown=true`:

- Prez still asks Lucene for a bounded hit window
- Prez does not apply a second SPARQL page slice in the umbrella subselect
- request `offset` is not yet pushed into Lucene as a native Lucene offset

That last point matters: enabling pushdown is the right default when filtering and ordering are fully handled in Lucene/CQL, but true Lucene offset pushdown is still future work.

## Why The Outer SPARQL Slice Is Disabled

Lucene matches are not one-row-per-hit once `luc:match` is expanded.

Conceptually, one Lucene hit can become multiple SPARQL rows:

```text
10 Lucene hits -> 30 SPARQL rows
```

So an outer SPARQL `LIMIT 10 OFFSET 0` is no longer a reliable page boundary for hits. It slices expanded match rows, not Lucene hits.

That is why the umbrella query now avoids applying a second page slice when pushdown mode is enabled.

## Limit Behavior

Current precedence for the Lucene hit limit is:

1. `fts_limit`, if set
2. otherwise use the request `limit`

This keeps the limit configuration explicit.

## Offset Behavior

`lucene_limit_offset_pushdown=true` means Prez stops pretending SPARQL `OFFSET` is a safe substitute for Lucene hit pagination on the expanded match rows.

Native Lucene offset pushdown has not been implemented yet.

Until that lands, the safe current behavior is:

- allow Lucene to control the hit window size
- avoid applying a misleading outer SPARQL `OFFSET`
- document that deep paging semantics are incomplete in pushdown mode

## Long-Term Direction

The intended end state is:

- Lucene receives both limit and offset
- Lucene returns only the requested hit window
- SPARQL does not re-slice expanded match rows

That will make hit counts, facet counts, and match expansion line up cleanly on the Lucene-backed path.
