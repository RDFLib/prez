# Lucene-Backed CQL and Queryables Discovery

**Date**: 2026-03-23

## Summary

Prez now has a feature-flagged Lucene-backed `/cql` implementation.

When the feature flag is disabled, `/cql` keeps its existing behavior.

When the feature flag is enabled, `/cql`:

- accepts Lucene-backed `q`, `filter`, and `facets` inputs
- validates that CQL `property` values are IRIs
- uses Jena Lucene `luc:query` inside the normal Prez listing/query/render pipeline
- maps Lucene `totalHits` to `prez:count`
- maps Lucene facet results into Prez facet RDF when `facets` is requested
- keeps Prez content negotiation and profile negotiation
- keeps annotation enrichment and Prez link generation
- keeps existing `facet_profile` support when Lucene `facets` is not used

The same feature also extends OGC Features `/queryables` so that Lucene-capable synthetic queryables loaded into the system store can be exposed to clients.

## Configuration

The feature is controlled by the following settings:

- `enable_cql_jena_lucene_json`
- `fts_limit`
- `lucene_limit_offset_pushdown`
- `lucene_index_name`
- `jena_fuseki_dataset_name`
- `jena_assembler_path`

Validation rules:

- `fts_limit` must be positive when set
- `lucene_index_name` must be a non-empty string
- when `enable_cql_jena_lucene_json=true`, `jena_fuseki_dataset_name` must be set
- when `enable_cql_jena_lucene_json=true`, `sparql_repo_type` must be `remote`
- when `jena_assembler_path` is set, `jena_fuseki_dataset_name` must be set

This implementation is intended for a remote Fuseki-compatible SPARQL endpoint. Local `pyoxigraph` stores do not support `luc:query`.

`lucene_index_name` defaults to `default` and is emitted as the leading Lucene property-function argument in `luc:query` and `luc:facet`.

`fts_limit` is the primary Lucene hit cap. When set, Prez uses it for both Fuseki FTS and Jena Lucene JSON searches.

`lucene_limit_offset_pushdown` controls whether Jena Lucene listing queries omit the outer SPARQL `LIMIT/OFFSET` and rely on Lucene-side pagination semantics instead. It defaults to `true`.

`jena_assembler_path` is optional and points at a Turtle Jena assembler file that Prez will parse during startup to generate Lucene queryables.

Startup queryables generation via `jena_assembler_path` is independent from the Lucene `/cql` feature flag. You can generate and expose `/queryables` from the assembler without enabling the Lucene-backed `/cql` router.

## Request Contract

### GET `/cql`

Accepted parameters:

- `q`: optional string, defaults to `*`
- `filter`: optional JSON string, must parse to an object
- `facets`: optional repeated query params of Lucene field IRIs
- `facet_profile`: optional existing Prez facet profile IRI
- `limit`: optional positive integer, defaults to the normal Prez listing limit
- `offset`: optional non-negative integer, defaults to `0`

Example:

```http
GET /cql?q=ore&limit=5&offset=10&facets=urn:jena:lucene:field#commodity&facets=urn:jena:lucene:field#state&filter={"op":"=","args":[{"property":"urn:jena:lucene:field#commodity"},"gold"]}
```

### POST `/cql`

Accepted JSON body:

```json
{
  "q": "ore",
  "filter": {
    "op": "=",
    "args": [
      { "property": "urn:jena:lucene:field#commodity" },
      "gold"
    ]
  },
  "facets": [
    "urn:jena:lucene:field#commodity",
    "urn:jena:lucene:field#state"
  ],
  "limit": 5,
  "offset": 10
}
```

Validation rules:

- `filter` must be a JSON object when present
- every `filter.args[].property` must be an absolute IRI
- GET `facets` must be repeated query params
- POST `facets` must be an array of IRI strings
- requested facet IRIs must be valid facetable Lucene queryables
- `facets` and `facet_profile` cannot be used together
- invalid `limit` or `offset` return `400`

The endpoint now behaves like the legacy Prez `/cql` route:

- mediatype negotiation is honored
- profile negotiation is honored
- `application/sparql-query` can be requested to inspect the generated queries
- normal Prez renderers are used for non-SPARQL-query responses
- Lucene hit score is exposed via `prez:searchResultWeight`
- Lucene total hits is exposed via `prez:count`
- Lucene facet rows are exposed via `prez:facetName`, `prez:facetValue`, and `prez:facetCount`

## Queryables Behavior

The existing OGC Features endpoints are reused inside the mounted OGC Features API:

- `/queryables`
- `/collections/{collectionId}/queryables`

In this Prez app, OGC Features is mounted under:

```text
/catalogs/{catalogId}/collections/{recordsCollectionId}/features
```

So the effective deployed queryables URLs are shaped like:

```text
/catalogs/{catalogId}/collections/{recordsCollectionId}/features/queryables
/catalogs/{catalogId}/collections/{recordsCollectionId}/features/collections/{collectionId}/queryables
```

For this feature, Prez loads `cql:Queryable` resources into the system store during normal startup loading. Prez does not parse the Fuseki assembler dynamically at request time.

Queryables can come from three startup sources:

- generated from `jena_assembler_path`
- remote explicit queryables from the configured SPARQL endpoint
- local explicit queryables from reference data files

Local queryables files are loaded from:

- `prez/reference_data/queryables/`
- or `$PREZ_REFERENCE_DATA_DIR/queryables/` when `PREZ_REFERENCE_DATA_DIR` is set

Prez loads `*.ttl` and `*.rdf` files from that directory at startup.

When `jena_assembler_path` is configured, Prez:

- parses the assembler file at startup
- uses `jena_fuseki_dataset_name` to select the `fuseki:Service`
- transforms Lucene `text:shapes` field definitions into synthetic queryables
- merges those generated queryables with any remote/local explicit queryables
- fails startup if the configured assembler path is missing, not a file, or invalid Turtle

Merge precedence is:

- local explicit queryables
- remote explicit queryables
- generated assembler queryables

Merge identity is based on `dcterms:identifier`, not RDF subject identity. That means an explicit local or remote queryable can override a generated one by reusing the same `dcterms:identifier` even if it uses a different RDF subject.

Generated assembler queryables use the Lucene field IRI as both:

- the RDF subject
- the `dcterms:identifier` string literal value

Generated assembler queryables also include:

- `a cql:Queryable`
- `a sh:PropertyShape`
- `sh:path`

Example:

```turtle
@prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix prez: <https://prez.dev/ont/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<urn:jena:lucene:field#commodity>
    a cql:Queryable, sh:PropertyShape ;
    dcterms:identifier "urn:jena:lucene:field#commodity" ;
    sh:name "commodity" ;
    sh:description "Lucene indexed field commodity" ;
    sh:datatype xsd:string ;
    sh:path <http://example.org/mining/commodity> ;
    prez:facetable true .
```

When synthetic Lucene queryables are present, `/queryables` JSON can expose Lucene-specific vendor extensions such as:

```json
{
  "x-prez-facetable": true,
  "x-prez-sortable": true,
  "x-prez-default-search": false,
  "x-prez-multi-valued": true,
  "x-prez-stored": true,
  "x-prez-indexed": true,
  "x-prez-lucene-field-type": "keyword"
}
```

The currently supported Lucene queryables extensions are:

- `x-prez-facetable`
- `x-prez-sortable`
- `x-prez-default-search`
- `x-prez-multi-valued`
- `x-prez-stored`
- `x-prez-indexed`
- `x-prez-lucene-field-type`

`x-prez-lucene-field-type` is the frontend-facing signal for how the field is indexed:

- `text`
- `keyword`
- `int`
- `long`
- `double`

`LatLonField` is still skipped by the current queryables transform, so it is not exposed through these JSON extensions yet.

For v1, global and local queryables return the same loaded dataset-derived set.

## Jena Assembler Transform Endpoint

Prez also exposes a management convenience endpoint for generating synthetic queryables from a Jena assembler:

```text
POST /jena-assembler-to-queryables
Content-Type: text/turtle
```

Behavior:

- accepts a Jena assembler in Turtle
- uses the configured `jena_fuseki_dataset_name` to select the `fuseki:Service`
- transforms the Lucene `text:shapes` field definitions into synthetic `cql:Queryable` RDF
- returns generated Turtle
- does not write files
- does not load the generated queryables into the running instance

This endpoint is a pure transform and remains useful for inspection/debugging.

The normal runtime path is now startup generation via `jena_assembler_path`, not saving the transform output into `reference_data/queryables`.

Saving the returned Turtle into:

- `prez/reference_data/queryables/`
- or `$PREZ_REFERENCE_DATA_DIR/queryables/`

is still valid if you want explicit file-based queryables, and those explicit queryables will override generated ones when they share the same `dcterms:identifier`.

## Property IRIs in Filters

For the Lucene-backed `/cql` feature, the `property` value in the CQL filter should be the same synthetic field IRI exposed via `/queryables`.

That means this is the intended form:

```json
{
  "filter": {
    "op": "=",
    "args": [
      { "property": "urn:jena:lucene:field#commodity" },
      "gold"
    ]
  }
}
```

and not a separate domain predicate IRI that Prez would remap later. The current implementation validates the IRI and passes it through unchanged into the Lucene filter JSON.

## Representative SPARQL Shape

This is the readable main query shape generated inside the Prez listing pipeline for the POST example above:

```sparql
PREFIX luc: <urn:jena:lucene:index#>
CONSTRUCT {
  ?hashID <https://prez.dev/searchResultURI> ?focus_node .
  ?hashID <https://prez.dev/searchResultPredicate> ?pred .
  ?hashID <https://prez.dev/searchResultMatch> ?match .
  ?hashID <https://prez.dev/searchResultWeight> ?weight .
  ?hashID a <https://prez.dev/SearchResult> .
  <https://prez.dev/SearchResult> <https://prez.dev/count> ?totalHits .
}
WHERE {
  {
    SELECT DISTINCT ?focus_node ?pred ?match ?weight ?totalHits
      (URI(CONCAT('urn:hash:', SHA256(CONCAT(STR(?focus_node), STR(?pred), STR(?match), STR(?weight))))) AS ?hashID)
    WHERE {
      {
        (?focus_node ?weight ?match ?totalHits ?g ?pred) luc:query (
          'default'
          'ore'
          '{"op":"=","args":[{"property":"urn:jena:lucene:field#commodity"},"gold"]}'
          16
        ) .
        FILTER (isIRI(?focus_node))
      }
    }
    ORDER BY DESC(?weight)
    LIMIT 6
    OFFSET 10
  }
}
```

Notes:

- omitted `q` becomes `*`
- omitted `filter` means no Lucene filter argument is passed
- Lucene's internal limit is expanded to `offset + limit + 1` so Prez paging still works through the normal listing pipeline
- the outer listing query still uses normal Prez `LIMIT` and `OFFSET`
- when `facets` is requested, Prez generates a second Lucene `CONSTRUCT` query that maps `luc:facet` rows into `prez:facetName`, `prez:facetValue`, and `prez:facetCount`
- `application/sparql-query` returns all generated queries joined with comment headers such as `# Query 1` and `# Query 2`

## Non-Goals

This feature does not:

- modify `/search`
- compute enum values or available facet values offline
- add a new discovery endpoint
- add special runtime reload behavior for transformed queryables
