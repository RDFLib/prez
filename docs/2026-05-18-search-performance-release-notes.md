# 2026-05-18 Search Performance Release Notes

## Summary

This investigation identified two distinct causes of slow `/search` responses:

1. Cold annotated responses were dominated by annotation cache misses, especially the local `annotations_repo` lookup path.
2. Warm responses were dominated by response emission overhead caused by returning `StreamingResponse(BytesIO(...))` for bodies that were already fully serialized in memory.

The second issue was the main cause of the multi-second warm-path slowdown in cloud.

## Key Fix

RDF response paths that already had a fully materialized in-memory body were changed to return `Response(content=bytes, ...)` instead of `StreamingResponse(BytesIO(...))`.

This reduced response chunk counts from thousands of tiny chunks to a single chunk and collapsed warm cloud response times from multi-second to sub-second / low-one-second ranges.

Observed effect on the deployed cloud instance:

- `text/turtle` dropped from roughly `4-8s` to roughly `0.6-1.0s`
- warm `text/anot+turtle` dropped from roughly `5-7s` to roughly `0.8-1.1s`

## Logging Policy

Timing CSV support remains available, but is now disabled by default:

- `TIMING_CSV_ENABLED=false`
- default path remains `logs/prez-timing.csv`

The retained timing events are the ones that proved useful in diagnosing real production behavior:

- `request_complete`
  - full request timing, chunk count, first/final body timing
- `remote_sparql_oxigraph_store`
  - backend fetch/read/bulk-load timing for RDF result loading
- `remote_sparql_tabular_query`
  - backend timing for tabular support queries
- `remote_sparql_proxy`
  - `/sparql` proxy timing
- `annotations_cache_lookup`
  - cache hit/miss visibility for annotation terms
- `annotations_uncached_terms`
  - cold annotation fallback timing, including local annotations repo cost
- `listing_query`
  - top-level listing query timing
- `listing_link_generation`
  - aggregate link-generation timing
- `listing_function_complete`
  - top-level listing total and render timing
- `return_rdf_from_oxigraph`
  - non-annotated RDF serializer timing
- `return_from_graph_annotated_oxigraph`
  - annotated RDF timing

The following investigation-only probes were removed to reduce noise:

- per-step link generation events such as:
  - `link_generation_uri_collection`
  - `link_generation_get_classes`
  - `link_generation_cache_split`
  - `link_generation_nodeshapes`
  - `link_generation_component_query`
  - `link_generation_generate_and_add`
- `annotation_term_collection`
- detailed `ogc_features_listing_*` CSV events
- one-off response-class confirmation logs
- low-value transport split rows that duplicated higher-level events

## Docker / Debug Dependency Cleanup

The temporary Docker image install of `tabulate` was removed.

`tabulate` is only used in a debug-only path in `connegp_service`. That path now degrades cleanly if `tabulate` is unavailable, so the production image no longer needs the dev dependency.

## Remaining Performance Observation

Cold annotated responses can still be slower because annotation misses still have to resolve against the local annotations source and then populate cache state.

That is a separate issue from the warm response emission bug and is now isolated much more clearly by the retained timing events.
