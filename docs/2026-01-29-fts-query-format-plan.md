# FTS Query Generation Update Plan

**Date**: 2026-01-29

## Background

Current FTS node shape query generation emits multiple UNION branches, each with its own `text:query` clause and an OPTIONAL path from `?fts_search_node` to `?focus_node`, guarded by `BOUND()`/`!isBLANK()` checks. The desired update consolidates predicates into a single `text:query` list, simplifies UNION branches, and adds a predicate-specific match triple to restrict branch evaluation to the relevant shape.

## Target Query Shape (Sketch)

```sparql
(?fts_search_node ?weight ?match ?g ?pred)
  <http://jena.apache.org/text#query>
  (
    <predA>
    <predB>
    <predC>
    "Bonaparte"
  ) .

{
  ?focus_node <pathA> ?fts_search_node .
  ?fts_search_node <predA> ?match .
}
UNION
{
  ?fts_search_node <pathB> ?focus_node .
  ?fts_search_node <predB> ?match .
}
UNION
{
  ?focus_node <pathC> ?fts_search_node .
  ?fts_search_node <predC> ?match .
}
```

Notes:
- The `text:query` list includes *all* predicates from relevant `ont:searchPredicate` values.
- Each UNION branch adds `?fts_search_node <shape_pred> ?match` to bind matches to that shape’s predicate.
- Optional/BIND/FILTER checks are removed; branch patterns are direct triples.

## Requirements Summary

1. **Collect all FTS predicates** from the active FTS node shapes via `ont:searchPredicate`.
2. **Emit a single `text:query` clause** containing all collected predicates and the search string.
3. **Simplify branch patterns** to plain triple patterns (no OPTIONAL + BOUND + isBLANK).
4. **Add predicate-specific match triple** in each UNION branch:
   - `?fts_search_node <shape_predicate> ?match`
   - Ensures that the branch only matches results indexed by that predicate.

## Implementation Plan

1. **Locate FTS query generation**
   - Find the function/module that builds the FTS UNION blocks and `text:query` triples (likely in query generation / SHACL handling code).
   - Identify how `ont:searchPredicate` is currently extracted and how separate `text:query` clauses are emitted.

2. **Aggregate predicates**
   - From the selected FTS node shapes, collect all unique `ont:searchPredicate` IRIs.
   - Preserve deterministic ordering (e.g., insertion order or sorted) to keep output stable.

3. **Build consolidated `text:query`**
   - Replace multiple `text:query` clauses with a single one that lists all collected predicates followed by the search literal (and any weighting/limit values currently used).
   - Confirm the desired output order inside the list (predicates first, then the search string).

4. **Rewrite UNION branches**
   - For each FTS node shape:
     - Replace OPTIONAL path + `BOUND`/`isBLANK` filter with direct triple patterns.
     - Add the extra predicate-specific match triple:
       `?fts_search_node <shape_predicate> ?match`.
   - Ensure branch-specific path direction is preserved (some shapes go from `?focus_node` to `?fts_search_node`, others the reverse).

5. **Validate generated query structure**
   - Add or update unit tests / snapshot tests to cover:
     - Multiple FTS node shapes with different `ont:searchPredicate` values.
     - Mixed path directions to `?focus_node`.
     - Duplicate predicates across shapes (dedupe in `text:query`, but still emit per-branch match triple).

6. **Review execution semantics**
   - Confirm that `?match` remains bound via `text:query` and is compatible with the added match triple.
   - Ensure the additional match triple does not unintentionally exclude valid results (verify with a representative dataset).

## Open Questions / Decisions

- **Predicate list order**: Should it be stable via sorting, or preserve the original shape ordering?
- **Duplicate predicates**: Use a set for `text:query` but still reference the predicate in each branch?
- **Weight/limit placement**: If weights or limits are appended after the literal in current queries, keep the same ordering when consolidating.
- **Branch duplication**: The provided sample shows a duplicate UNION branch; confirm whether duplicates should be removed or preserved.

## Suggested Tests

- One FTS shape with a single `ont:searchPredicate`.
- Multiple shapes with distinct predicates.
- Multiple shapes sharing the same predicate.
- Mix of path directions (`?focus_node → ?fts_search_node` and `?fts_search_node → ?focus_node`).
- Ensure the query still filters out blank focus nodes if needed elsewhere (if that logic moves, it should be explicit).
