# 2026-05-15 Prez Search Performance And Annotation Path Design

## Summary

Recent benchmarking of `POST /search` with:

- `_profile=search-metadata`
- `limit=1000`
- CQL `s_intersects`
- Lucene geometry field `urn:jena:lucene:field#geometry`

shows that the main 1k spatial search is not the dominant problem. The main query path is generally fast and stable once the query is generated correctly. The large latency spikes are concentrated in the annotation enrichment path for annotated RDF responses.

This note summarizes the findings and proposes a design direction for reducing cold-start and semi-cold annotated response latency.

## Main Findings

### 1. Direct Fuseki Is Not The Bottleneck

Across local and cloud testing, direct Fuseki execution of the generated SPARQL was consistently much faster than `/search`.

Warm `/sparql` via Prez was also close to direct Fuseki, which strongly suggests the large overhead is specific to the `/search` listing/rendering path rather than to Prez as a generic proxy.

### 2. `bbox` Was Not Reliable For This Investigation

For this deployment, the `bbox` parameter did not appear to provide a trustworthy filtered count path. The reliable path was:

- `POST /search`
- CQL `s_intersects`
- property IRI `urn:jena:lucene:field#geometry`

### 3. `search-metadata` Is A Good Working WKT Profile

`search-metadata` returns coordinate WKT values in the response and worked well for benchmarking machine-facing search responses.

### 4. PR #384 Mostly Helped The Right Parts

The local merged history for PR `#384` (`21327e5a`, `feat: oxigraph sparql responses`) shows a strong push toward Oxigraph-backed response handling:

- Oxigraph RDF response handling across repo types
- Oxigraph serialization support
- Oxigraph-based annotations handling
- bulk link generation support
- removal of unnecessary RDFLib-to-Oxigraph double handling

The follow-up commit `495f35b8` further reordered annotation lookup so that:

1. `system_repo` is queried first
2. `annotations_repo` is queried second
3. `data_repo` is queried only for remaining terms

This matches the current implementation.

The measured timings suggest that these changes were effective for:

- main RDF fetch/materialization
- Oxigraph load
- plain Turtle render/dump

Those phases are relatively cheap now.

### 5. The Remaining Hotspot Is Cold Annotation Enrichment

The dominant cost in slow annotated `/search` responses is the annotation miss path.

Important distinction:

- the **annotation cache** is a runtime memoization layer
- the **annotations repo/store** is the local source of annotation RDF

An "annotation miss" means:

- annotation metadata for a term was not already present in the runtime cache

It does **not** mean:

- a remote Fuseki miss
- a missing annotation in the local source dataset

### 6. The Local Annotations Repo Is The Dominant Cold Cost

The local `annotations_repo` is currently:

- `PyoxigraphRepo(annotations_store)`
- where `annotations_store` is loaded from `reference_data/annotations/*`

Current annotation miss behavior is batched, not term-by-term:

- one batch query to `system_repo`
- one batch query to `annotations_repo`
- one batch query to `data_repo` only if needed

Even so, the cloud cold-path timings show the largest cost is the batched query against the local `annotations_repo`, not the remote main triplestore.

## Measured Behavior

### Local

For the 1k `search-metadata` search:

- plain `text/turtle` was fast and mainly spent time in the main query path
- warm `text/anot+turtle` was only modestly slower
- cold `text/anot+turtle` was much slower due to annotation misses and class/link lookup

Representative interpretation:

- main query/materialization: low hundreds of milliseconds
- plain render/dump: very small
- cold annotation path: dominant
- warm annotation path: much cheaper

### Cloud

With one worker, the cloud timings became very clear:

- plain `text/turtle`: about `495 ms`
- warm `text/anot+turtle`: about `608 ms`
- cold `text/anot+turtle`: about `5820 ms`

The cold annotated blowout was overwhelmingly annotation work, and within that, overwhelmingly the local `annotations_repo` phase for uncached terms.

The main query stayed roughly stable across Turtle, warm annotated, and cold annotated runs.

## Current Architecture

The annotation path currently looks like this:

1. collect subjects, predicates, object IRIs, and datatypes from the item store
2. look up all terms in the runtime cache
3. for uncached terms:
   - query `system_repo`
   - query `annotations_repo`
   - query `data_repo` only for remaining terms
4. cache the resolved result set
5. merge annotations into the response store

This means the local annotations source is currently being used as a generic queryable repo, even though it is only serving one fixed lookup purpose.

## Design Direction

### Recommendation

Keep the current runtime cache, but replace the local `annotations_repo` query path with a purpose-built local annotation lookup structure.

The cleanest version is:

- keep the existing annotation cache
- replace local `annotations_repo` SPARQL lookups with a preloaded in-memory key-value structure
- keep `data_repo` fallback for anything still unresolved

### Why

The local annotations source is:

- static at runtime
- loaded from local files at startup
- used for a fixed access pattern

The current access pattern is much closer to:

- `subject -> small set of annotation predicate/object pairs`

than to a general SPARQL workload.

That makes a preloaded lookup structure a better fit than repeatedly running generic batch SPARQL queries over the local annotations graph.

### Why Not Just Remove The Cache

The runtime cache is still useful because it can hold:

- resolved local annotation results
- results coming from `system_repo`
- results coming from `data_repo`
- empty / negative results

So the recommended model is:

1. keep the current cache as the front door
2. replace the local annotations source behind that cache with a faster local lookup structure

### Why Not Add Another General Cache Layer

Using another `aiocache` instance as the local source is less attractive than a plain in-memory structure because:

- the local annotation dataset is static
- there is no need for TTL/eviction semantics for the source layer
- a plain dict-like structure is simpler and likely faster

## Proposed Runtime Flow

For annotation resolution:

1. check the current runtime annotation cache
2. for misses, check a preloaded local annotation index
3. for remaining misses, query `data_repo`
4. cache final results in the existing runtime cache

This preserves current semantics while removing the most expensive local batched annotation query path.

## Implementation Notes

### Minimal-Change Version

Implement a new dependency/service such as:

- `get_local_annotation_index()`

and update `process_uncached_terms_for_oxigraph()` to:

- resolve against the local index instead of calling `annotations_repo.send_queries(...)`

The value shape can remain aligned with the existing cache:

- `dict[URIRef, frozenset[(URIRef, Node)]]`

or equivalent Oxigraph-friendly internal form.

### Keep The Existing Cache

The current runtime cache should remain in place. It already provides the right overall semantics for repeated requests and mixed local/system/data-sourced annotations.

### Optional Follow-Up Improvements

- reduce the term set fed into annotation lookup
  - today all subjects, predicates, object IRIs, and datatypes are considered
- add negative caching explicitly and consistently
- reduce or disable link generation for response types that do not benefit from it
- optionally warm common annotation terms at startup

## Conclusion

The evidence now points to a narrow problem:

- the expensive part is not the main 1k spatial search
- it is not plain Turtle serialization
- it is not raw remote Fuseki latency

The expensive cold path is the local annotation miss resolution phase, especially the batched lookup against the local annotations repo.

The recommended next design step is therefore:

- keep the existing runtime annotation cache
- replace local annotations repo querying with a direct in-memory annotation lookup structure
- preserve `data_repo` fallback for anything not covered locally

This is the cleanest way to attack the measured hotspot without undoing the broader Oxigraph work introduced by PR `#384`.
