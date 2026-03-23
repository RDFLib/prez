# Lucene-Backed CQL and Queryables Discovery

**Date**: 2026-03-23

## Summary

Prez now has a feature-flagged Lucene-backed `/cql` implementation that is separate from the existing CQL listing pipeline.

When the feature flag is disabled, `/cql` keeps its existing behavior.

When the feature flag is enabled, `/cql`:

- accepts raw Lucene-backed `q`, `filter`, and `facets` inputs
- validates that CQL `property` values are IRIs
- executes raw SPARQL with `luc:query` and optional `luc:facet`
- always returns `application/sparql-results+json`
- ignores Prez content negotiation and profile negotiation for this endpoint

The same feature also extends OGC Features `/queryables` so that Lucene-capable synthetic queryables loaded into the system store can be exposed to clients.

## Configuration

The feature is controlled by the following settings:

- `enable_cql_jena_lucene_json`
- `lucene_default_limit`
- `jena_fuseki_dataset_name`

Validation rules:

- `lucene_default_limit` must be a positive integer
- when `enable_cql_jena_lucene_json=true`, `jena_fuseki_dataset_name` must be set
- when `enable_cql_jena_lucene_json=true`, `sparql_repo_type` must be `remote`

This implementation is intended for a remote Fuseki-compatible SPARQL endpoint. Local `pyoxigraph` stores do not support `luc:query`.

## Request Contract

### GET `/cql`

Accepted parameters:

- `q`: optional string, defaults to `*`
- `filter`: optional JSON string, must parse to an object
- `facets`: optional repeated query params only
- `limit`: optional positive integer, defaults to `lucene_default_limit`
- `offset`: optional non-negative integer, defaults to `0`

Example:

```http
GET /cql?q=ore&limit=5&offset=10&facets=file:///fuseki/config.ttl#field-commodity&facets=file:///fuseki/config.ttl#field-state&filter={"op":"=","args":[{"property":"file:///fuseki/config.ttl#field-commodity"},"gold"]}
```

### POST `/cql`

Accepted JSON body:

```json
{
  "q": "ore",
  "filter": {
    "op": "=",
    "args": [
      { "property": "file:///fuseki/config.ttl#field-commodity" },
      "gold"
    ]
  },
  "facets": [
    "file:///fuseki/config.ttl#field-commodity",
    "file:///fuseki/config.ttl#field-state"
  ],
  "limit": 5,
  "offset": 10
}
```

Validation rules:

- `filter` must be a JSON object when present
- every `filter.args[].property` must be an absolute IRI
- GET `facets` must be repeated query params
- POST `facets` must be an array of strings
- requested facet IRIs must be present in the facetable synthetic queryables set
- invalid facet IRIs return `400`
- invalid `limit` or `offset` return `400`

The endpoint always returns:

```http
Content-Type: application/sparql-results+json
```

## Queryables Behavior

The existing OGC Features endpoints are reused:

- `/queryables`
- `/collections/{collectionId}/queryables`

For this feature, Prez expects synthetic `cql:Queryable` resources to be loaded into the system store during normal startup loading. Prez does not parse the Fuseki assembler dynamically at request time.

Each synthetic queryable should use the Lucene field IRI as both:

- the RDF subject
- the `dcterms:identifier` string literal value

Example:

```turtle
@prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix prez: <https://prez.dev/ont/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<file:///fuseki/config.ttl#field-commodity>
    a cql:Queryable ;
    dcterms:identifier "file:///fuseki/config.ttl#field-commodity" ;
    sh:name "commodity" ;
    sh:description "Lucene indexed field commodity" ;
    sh:datatype xsd:string ;
    prez:facetable true .
```

When `prez:facetable true` is present, `/queryables` JSON exposes:

```json
{
  "x-prez-facetable": true
}
```

For v1, global and local queryables return the same loaded dataset-derived set.

## Property IRIs in Filters

For the Lucene-backed `/cql` feature, the `property` value in the CQL filter should be the same synthetic field IRI exposed via `/queryables`.

That means this is the intended form:

```json
{
  "filter": {
    "op": "=",
    "args": [
      { "property": "file:///fuseki/config.ttl#field-commodity" },
      "gold"
    ]
  }
}
```

and not a separate domain predicate IRI that Prez would remap later. The current implementation validates the IRI and passes it through unchanged into the Lucene filter JSON.

## Representative SPARQL Shape

This is the readable query shape generated for the POST example above:

```sparql
PREFIX luc: <urn:jena:lucene:index#>
SELECT ?focus_node ?score ?literal ?graph ?property ?facet_field ?facet_value ?facet_count
WHERE {
{
  (?focus_node ?score ?literal ?graph ?property) luc:query (
    'ore'
    '{"op":"=","args":[{"property":"file:///fuseki/config.ttl#field-commodity"},"gold"]}'
    5
  ) .
}
UNION
{
  (?facet_field ?facet_value ?facet_count) luc:facet (
    'ore'
    '["file:///fuseki/config.ttl#field-commodity","file:///fuseki/config.ttl#field-state"]'
    '{"op":"=","args":[{"property":"file:///fuseki/config.ttl#field-commodity"},"gold"]}'
  ) .
}
}
LIMIT 5
OFFSET 10
```

Notes:

- omitted `q` becomes `*`
- omitted `filter` means no Lucene filter argument is passed
- omitted `facets` means no `luc:facet` branch is generated
- `LIMIT` and `OFFSET` are standard SPARQL pagination

## Non-Goals

This feature does not:

- modify `/search`
- integrate the Lucene `/cql` route into the legacy listing/rendering pipeline
- compute enum values or available facet values offline
- add a new discovery endpoint
- add special runtime reload behavior for transformed queryables
