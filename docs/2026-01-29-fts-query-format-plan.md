# FTS Query Generation Update Plan

**Date**: 2026-01-29

## Background

Current FTS node shape query generation emits multiple UNION branches, each with its own `text:query` clause and an OPTIONAL path from `?fts_search_node` to `?focus_node`, guarded by `BOUND()`/`!isBLANK()` checks. The desired update consolidates predicates into a single `text:query` list and simplifies UNION branches to direct path triples with a not‑blank filter on `?focus_node`.

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
}
UNION
{
  ?fts_search_node <pathB> ?focus_node .
}
UNION
{
  ?focus_node <pathC> ?fts_search_node .
}
```

Notes:
- The `text:query` list includes *all* predicates from relevant `ont:searchPredicate` values.
- UNION branches are the path patterns only (plus not‑blank checks).
- Optional/BIND/FILTER checks are removed; branch patterns are direct triples.

## Requirements Summary

1. **Collect all FTS predicates** from the active FTS node shapes via `ont:searchPredicate`.
2. **Emit a single `text:query` clause** containing all collected predicates and the search string.
3. **Simplify branch patterns** to plain triple patterns (no OPTIONAL + BOUND + isBLANK).
4. **Support SHACL-AF union containers** for FTS shapes:
   - Allow a standalone node expression (identified by `dcterms:identifier`) with `sh:union ( ... )`
   - Each union member is a path expression (blank node with `sh:path`) and may include `ont:searchPredicate`
   - Translate each member into a separate UNION branch, same as if the member were a normal FTS property shape.

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
     - Apply `FILTER(!isBLANK(?focus_node))` as needed.
   - Ensure branch-specific path direction is preserved (some shapes go from `?focus_node` to `?fts_search_node`, others the reverse).

5. **Validate generated query structure**
   - Add or update unit tests / snapshot tests to cover:
     - Multiple FTS node shapes with different `ont:searchPredicate` values.
     - Mixed path directions to `?focus_node`.
     - Duplicate predicates across shapes (dedupe in `text:query`).

6. **Review execution semantics**
   - Confirm that `?match` remains bound via `text:query` and is available for CONSTRUCT output.

## Open Questions / Decisions

- **Predicate list order**: Should it be stable via sorting, or preserve the original shape ordering?
- **Duplicate predicates**: Use a set for `text:query` but still reference the predicate in each branch?
- **Weight/limit placement**: If weights or limits are appended after the literal in current queries, keep the same ordering when consolidating.
- **Branch duplication**: The provided sample shows a duplicate UNION branch; confirm whether duplicates should be removed or preserved.
- **Property group IRIs (Fuseki config)**: Non‑SHACL predicates may be *property group* IRIs (e.g., `http://example.org/allprops`) that expand to multiple predicates in the Fuseki text index. These are not resolvable in Prez, so we cannot emit predicate‑specific match triples safely.
- **SHACL-AF union containers**: Decide how to surface these in config/docs and whether to require an explicit class (e.g., `ont:JenaFTSUnionShape`) or simply any node with `sh:union` and `dcterms:identifier`.

## Plan: FTS Union Containers (sh:union)

### Goal

Allow a **single `predicates=` value** to represent a union of multiple FTS property shapes by using `sh:union` on a standalone node expression. This becomes a declarative container for UNION branches.

### Expected Turtle Pattern (example)

```turtle
ex:interesting_objects
    dcterms:identifier "interesting_objects" ;
    sh:union (
        [ sh:path ex:firstName ; ont:searchPredicate rdfs:label ]
        [ sh:path ex:givenName ; ont:searchPredicate rdfs:label ]
        [ sh:path ex:title ; ont:searchPredicate dcterms:title ]
    ) .
```

### Implementation Steps

1. **Parse union container nodes**
   - In `get_jena_fts_shacl_predicates` / FTS shape parsing, detect nodes with `sh:union`.
   - Require `dcterms:identifier` so they can be referenced via `predicates=`.

2. **Expand union members into FTS shapes**
   - For each member node expression in the `sh:union` list:
     - Expect `sh:path` (path expression).
     - Read `ont:searchPredicate` (if missing, decide on fallback or skip).
   - Convert each member into a `PropertyShape` equivalent (reuse existing `PropertyShape` parsing if possible).

3. **Integrate with query generation**
   - Treat union members as if they were listed separately in `predicates=`.
   - Each member creates its own UNION branch (path triples only).

4. **Validation and errors**
   - If a union member lacks `sh:path` or `ont:searchPredicate`, return a clear config error.
   - If a union container is referenced in `predicates=` but has no resolvable members, ignore or error consistently.

5. **Tests**
   - One union container with two members (different paths, different predicates).
   - Union container mixed with normal FTS property shapes and non‑SHACL predicates.
   - Invalid union member (missing `sh:path`) → expected error.

### Documentation Updates

- Add a section to `docs/fuseki_fts_functionality.md` describing `sh:union` containers and how to use them.

## Clarification: Property Group IRIs

Fuseki text indices can define *property groups* where an IRI represents a collection of indexed predicates. When a non‑SHACL predicate equals a property group IRI, Prez cannot expand it into real predicates and therefore cannot emit a predicate‑specific triple.

### Proposed handling

- **Non‑SHACL predicates (possibly property groups)**:  
  Use a branch that **only** binds `?focus_node` to `?fts_search_node` and applies `FILTER(!isBLANK(?focus_node))`.  
  This avoids false negatives when the IRI is a property group, at the cost of less constraint in that branch.

- **SHACL predicates**:  
  Continue to emit only the path triples in each branch.

### Recommendation for precision

If users want predicate‑specific matching for a single property, advise creating a SHACL FTS shape with a single `ont:searchPredicate`. This provides a concrete predicate IRI for targeted configuration.

## Suggested Tests

- One FTS shape with a single `ont:searchPredicate`.
- Multiple shapes with distinct predicates.
- Multiple shapes sharing the same predicate.
- Mix of path directions (`?focus_node → ?fts_search_node` and `?fts_search_node → ?focus_node`).
- Ensure the query still filters out blank focus nodes if needed elsewhere (if that logic moves, it should be explicit).
