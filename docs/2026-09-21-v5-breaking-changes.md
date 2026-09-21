# 2026-09-21 Breaking Changes

Changes on this branch that break existing clients or downstream code. Prez is
at `4.7.5`; these are intended to land in the v5 line, so no backwards
compatibility shims are provided.

## 1. `POST /cql` request body must be wrapped in a `filter` key

The body was previously the CQL2-JSON expression itself. It is now a JSON object
carrying the expression under `filter`, alongside the listing parameters.

Before:

```json
{"op": "s_intersects", "args": [...]}
```

After:

```json
{"filter": {"op": "s_intersects", "args": [...]}, "limit": 10}
```

A body in the old shape is rejected:

```
400 Request body must contain a 'filter' key with the CQL2-JSON expression.
```

The wrapper exists because a POST body now carries the full listing parameter
set next to the filter - `limit`, `offset`, `page`, `startindex`, `_profile`,
`_mediatype`, `bbox`, `datetime`, `order_by`, `order_by_direction`, `q`,
`fields`, `facets`, `facet_profile`, `filter-lang`, `filter-crs`. None of those
can be expressed alongside a raw expression body.

**Migration:** wrap the existing expression in `{"filter": ...}`. Any listing
parameters previously sent as query string arguments can move into the same
object.

## 2. `POST /cql` requires `Content-Type: application/json`

Prez 4 did not inspect the request content type on this route. It is now
required:

```
415 Content-Type must be application/json
```

This breaks separately from the body shape, and is easier to miss: a client that
has migrated its body but sends no content type, or sends
`application/x-www-form-urlencoded`, still fails.

The same requirement applies to every POST endpoint added on this branch, but
`POST /cql` is the only one that existed before it, so it is the only one that
can break an existing client.

`POST /sparql` is unaffected - it does not go through the JSON body parser and
still accepts the SPARQL protocol content types.

## 3. `sparql-grammar-pydantic` replaced by `sparql-grammar`

```toml
- sparql-grammar-pydantic = "^0.1.10"
+ sparql-grammar = {git = "https://github.com/Kurrawong/sparql-grammar.git", rev = "main"}
```

This affects downstream code that imports Prez's query generation classes, or
that builds SPARQL with the same library alongside Prez. The two libraries are
not drop-in compatible: the new one uses slotted dataclasses rather than pydantic
models, flattens several recursive productions into lists, and exposes some bare
alternations as union aliases rather than classes.

Emitted SPARQL is unchanged except for one fix: `CollectionPath` now renders its
items separated rather than concatenated.

**Note for release:** the dependency is a git reference pinned to `main`, which
cannot be published to PyPI. It needs to become a released version or a tag
before a v5 release is cut.

## 4. `pyld` major version bump

```toml
- pyld = "^2.0.4"
+ pyld = "^3.0.0"
```

Relevant to anyone pinning `pyld` themselves in an environment shared with Prez.

Other dependency bumps on this branch are within their existing major versions:
`fastapi` `0.116` to `0.135`, `uvicorn` `0.35` to `0.44`, `rdflib` `7.0` to
`7.6`, `pydantic-settings` `2.5` to `2.13`, `pyoxigraph` `0.5.1` to `0.5.6`.

## Not breaking

Listed because they look like breaks in the diff and are not:

- **`/cql` GET and POST moved** out of `base_router.py` into `cql_router.py` and
  `cql_lucene_router.py`. The paths and endpoint names are unchanged.
- **Settings are additive.** Thirteen were added; none were removed, renamed, or
  had their defaults changed.
- **`testcontainers`** is a dev dependency, not a runtime one.
