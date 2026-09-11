# 2026-05-13 Prez Search and Fuseki Benchmark Notes

## Scope

This note captures ad hoc benchmark work on Prez spatial search against GSWA data, focused on:

- Lucene-backed CQL `s_intersects` polygon search
- returning up to 1000 rows
- comparing local vs cloud deployments
- separating Fuseki cost from Prez cost
- checking whether network path to Fuseki is a dominant factor

The main services involved were:

- local Prez: `http://localhost:8040`
- local Fuseki: `http://localhost:3030/gswads/sparql`
- cloud Prez: `https://prez-prod.yellowground-a7d78247.australiaeast.azurecontainerapps.io`
- cloud Fuseki: `http://20.11.43.102/gswads/sparql`

Later, the cloud Prez `/sparql` endpoint was enabled and tested separately.

## Query shape used

For meaningful spatial filtering, `bbox` was not reliable on this deployment. Large WA bboxes kept returning the same `prez:count`, while CQL `s_intersects` produced plausible filtered counts.

The reliable path was:

- `POST /search`
- `_profile=search-metadata`
- `_mediatype=text/anot+turtle` or `text/turtle`
- Lucene-backed CQL `s_intersects`
- geometry property IRI `urn:jena:lucene:field#geometry`

The CQL property must be an IRI on this path. `"geometry"` produced HTTP 400. This worked:

```json
{
  "_profile": "search-metadata",
  "limit": 1000,
  "filter": {
    "op": "s_intersects",
    "args": [
      { "property": "urn:jena:lucene:field#geometry" },
      {
        "type": "Polygon",
        "coordinates": [[[112.07,-36],[112.07,-26],[122.07,-26],[122.07,-36],[112.07,-36]]]
      }
    ]
  }
}
```

The polygon was shifted slightly between runs to reduce cache bias.

## Profiles and output

The default `/search` profile was `ogc-listing`, which is minimal and effectively just returns `rdf:type` plus search wrapper metadata.

For WKT-bearing output, the most useful loaded profile was `search-metadata`. In practice it returned coordinate WKT via the `coordinates` alias, for example:

```turtle
<https://example.org/coordinates> "POINT(115.0802361 -29.25309444)"^^geo:wktLiteral .
```

For a local `search-metadata` 1000-row response:

- coordinate predicate lines: `1001`
- `POINT(` occurrences: `1010`
- file size: `635982` bytes

So the 1000-row WKT response was only about `636 KB`.

## `bbox` vs `s_intersects`

Observed `bbox` behavior was suspicious:

- larger WA-ish bboxes repeatedly emitted `prez:SearchResult prez:count 84085337`
- a very small bbox returned zero hits and no count
- changing the bbox did not produce a useful varying filtered count once any hits existed

By contrast, the equivalent CQL `s_intersects` request returned a plausible filtered count:

- `prez:SearchResult prez:count 212464`

For the purposes of these benchmarks, `s_intersects` was treated as the valid spatial path and `bbox` was treated as not trustworthy for filtered-count analysis on this deployment.

## Local Prez timings

Using `_profile=search-metadata` against local Prez with local Fuseki:

| limit | mediatype | total time | size |
| --- | --- | ---: | ---: |
| 10 | `text/anot+turtle` | `0.178795s` | `19511` |
| 100 | `text/anot+turtle` | `0.617419s` | `75893` |
| 500 | `text/anot+turtle` | `1.691896s` | `324830` |
| 1000 | `text/anot+turtle` | `2.508872s` | `635982` |

For comparison, `ogc-listing` at 1000 rows came back in:

- `2.549956s`
- `311786` bytes

That was notable because `search-metadata` was not materially slower than the minimal listing profile on localhost, despite returning actual WKT-bearing metadata.

## Initial cloud Prez timings

Using the same query shape against cloud Prez:

| limit | mediatype | total time | size |
| --- | --- | ---: | ---: |
| 10 | `text/anot+turtle` | `0.703122s` | `19501` |
| 1000 | `text/anot+turtle` | `20.842695s` | `635991` |

The `20.84s` result later looked like a cold or transient outlier. Subsequent 1000-row cloud Prez runs with shifted polygons were:

- `8.328102s`
- `6.003705s`
- `5.923657s`
- `7.726441s`

This suggested the cloud Prez `/search` path was generally in the `~6s` to `~8s` range for this query, not `~20s`.

## Four-endpoint comparison

Using the same 1000-row query against all four services:

### Run 1

Polygon shifted to `112.04` / `122.04`:

| endpoint | total time | size |
| --- | ---: | ---: |
| cloud Fuseki | `0.591608s` | `961497` |
| cloud Prez `/search` | `7.358672s` | `636003` |
| local Fuseki | `0.314534s` | `992234` |
| local Prez `/search` | `1.744745s` | `636012` |

### Run 2

Polygon shifted to `112.05` / `122.05`:

| endpoint | total time | size |
| --- | ---: | ---: |
| cloud Fuseki | `0.573110s` | `961497` |
| cloud Prez `/search` | `8.328102s` | `636021` |
| local Fuseki | `0.207765s` | `992234` |
| local Prez `/search` | `1.398045s` | `636012` |

### Interpretation

The important signal was:

- direct cloud Fuseki was already fast
- local Fuseki was faster again, but not by an order of magnitude
- both Prez `/search` paths were much slower than their paired Fuseki endpoints
- Prez returned a smaller payload than direct Fuseki while still taking longer

This pointed away from Fuseki query execution as the main bottleneck and toward the Prez `/search` path.

## Cloud Prez `text/turtle`

Cloud Prez `/search` with `Accept: text/turtle` came back at:

- `4.635606s`
- `551055` bytes

Compared to cloud Prez `text/anot+turtle` at roughly `6s` to `8s`, plain Turtle was clearly faster and smaller. This showed that annotation and related rendering work contributes materially to `/search` latency.

However, even plain Turtle on cloud Prez was still much slower than direct cloud Fuseki, so annotation was not the whole story.

## Cloud resize test

Cloud Prez initially ran at approximately:

- `2 vCPU`
- `4 GB RAM`

Later it was restarted at:

- `4 vCPU`
- `8 GB RAM`

Post-resize cloud Prez `/search` runs were:

- `5.272708s`
- `7.086665s`
- exact-repeat of the first post-resize polygon: `7.273212s`

This suggested some improvement versus the slower pre-resize samples, but not a dramatic step-change. It did support the view that the `/search` path is resource-sensitive, especially on CPU.

## Local Prez pointed at cloud Fuseki

Local Prez was then reconfigured to use cloud Fuseki instead of local Fuseki.

Results:

- local Prez -> cloud Fuseki, `text/anot+turtle`: `3.933243s`, `636082` bytes
- local Prez -> cloud Fuseki, `text/turtle`: `2.259111s`, `551110` bytes
- direct cloud Fuseki reference: `0.556857s`, `961554` bytes

This established three things:

1. The remote Prez-to-Fuseki hop does matter.
2. It does not explain the full cloud `/search` slowdown on its own.
3. Annotation still adds a measurable cost.

Local Prez against cloud Fuseki remained much faster than cloud Prez against cloud Fuseki, so the cloud app/runtime environment was still a major factor.

## Generated SPARQL and direct Fuseki

Prez was asked for the generated SPARQL using `_mediatype=application/sparql-query`, and the resulting query was posted directly to Fuseki.

For the 1000-row generated query against cloud Fuseki:

- `0.574080s`
- `961554` bytes

Fresh rerun later:

- `0.606954s`
- `961554` bytes

This is the strongest evidence that cloud Fuseki itself was not slow for this workload.

## Cloud Prez `/sparql`

The cloud Prez deployment initially returned `404` on `/sparql`, because the route is only mounted when `enable_sparql_endpoint` is enabled. After it was opened, the same generated 1000-row query was tested through Prez `/sparql`.

Results:

- first run: `3.127164s`, `961554` bytes
- second run: `0.782409s`, `961554` bytes
- third run: `0.748409s`, `961554` bytes

Compared with direct cloud Fuseki:

- direct Fuseki: `0.606954s`, `961554` bytes

This is a critical result:

- warm Prez `/sparql` was only about `0.14s` to `0.18s` slower than direct Fuseki
- payload size was identical
- therefore the Prez app is capable of near-pass-through performance on the proxy path

This sharply narrows the likely source of the major slowdown to the `/search` path specifically, not to basic connectivity from the cloud app to Fuseki.

## Public vs private IP from the web app

From Kudu on the production web app, private connectivity to the Fuseki VM was confirmed:

- `curl http://10.0.0.4:3030/...` reached Jetty/Fuseki
- an `ASK` query succeeded against both private and public addresses

The measured private-vs-public difference for a simple query was negligible, around a couple of milliseconds.

This was unsurprising given that both services are in Azure and public routing may still remain on Microsoft-managed backbone paths.

The result does not mean private connectivity is useless, but it does mean:

- raw network path to Fuseki is not the main explanation for multi-second `/search` latency
- switching Prez from public IP to private IP alone is unlikely to produce a dramatic improvement

## Code-path findings

The current implementation explains the benchmark split between `/sparql` and `/search`.

### `/search`

Listings call:

- `data_repo.send_queries(..., return_oxigraph_store=True)` in [prez/services/listings.py](/home/david/PycharmProjects/prez/prez/services/listings.py:758)

For a remote SPARQL endpoint, this path:

- sends a query to Fuseki
- reads the full HTTP response with `await response.aread()`
- bulk-loads the RDF into an Oxigraph store

in [prez/repositories/remote_sparql.py](/home/david/PycharmProjects/prez/prez/repositories/remote_sparql.py:88).

Then `/search` may:

- issue a count query in parallel
- generate annotations for annotated formats
- serialize the result back out

This is consistent with the benchmark results: `/search` is doing real work beyond simple proxying.

### `/sparql`

The `/sparql` route is effectively a proxy:

- route in [prez/routers/sparql.py](/home/david/PycharmProjects/prez/prez/routers/sparql.py:24)
- forwarding in [prez/repositories/remote_sparql.py](/home/david/PycharmProjects/prez/prez/repositories/remote_sparql.py:118)

For plain RDF formats, Prez streams the backend response instead of materializing it into an Oxigraph store first. This matches the warm `/sparql` timings, which were close to raw Fuseki.

## Main findings

1. Cloud Fuseki was not slow for the tested 1000-row polygon search. Direct cloud Fuseki stayed around `0.57s` to `0.61s`.
2. The major slowdown sits in Prez `/search`, not in Fuseki query execution.
3. The warm Prez `/sparql` path is close to direct Fuseki performance, so the cloud app can reach Fuseki efficiently enough.
4. Annotation contributes materially to `/search` latency, but plain Turtle is still much slower than direct Fuseki, so annotation is not the whole explanation.
5. The likely expensive parts of `/search` are:
   - full response read
   - bulk load into Oxigraph
   - count query
   - annotation generation when requested
   - final serialization
6. Remote Prez-to-Fuseki distance does matter, but it does not explain the whole cloud-local gap.
7. Public vs private IP to Fuseki was not a meaningful differentiator in the tested Azure setup.

## Practical implications

If the goal is lower-latency bulk RDF delivery:

- prefer `/sparql` where possible
- treat `/search` as a more expensive result-construction path

If the goal is improving `/search`:

- instrument phase timings around:
  - backend query send/receive
  - `response.aread()`
  - `bulk_load(...)`
  - count query
  - annotation generation
  - serialization
- reduce extra backend round-trips where possible
- consider simpler or more direct RDF output paths for machine consumers

At this point, the evidence does not support blaming cloud Fuseki query latency for the observed `/search` performance.
