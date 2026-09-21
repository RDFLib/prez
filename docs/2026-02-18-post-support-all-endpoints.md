# POST Support for All Prez Listing Endpoints

**Date:** 2026-02-18
**Status:** Design proposal — no code changes yet

---

## 1. Motivation

### URL Length Limits

HTTP GET encodes all parameters in the query string. Browsers and servers impose practical limits (typically 2–8 KB). Prez listing endpoints support complex CQL2-JSON filter expressions that can easily exceed this limit:

- A CQL2-JSON spatial filter with a detailed polygon geometry can be thousands of characters.
- Multiple combined parameters (`filter`, `bbox`, `datetime`, `q`, `_profile`, etc.) compound the problem.
- URL-encoding of JSON adds roughly 30–50% overhead (spaces → `%20`, braces → `%7B`, etc.).

POST with a JSON body has no such practical limit and avoids encoding overhead.

### Existing Proof-of-Concept

`POST /cql` already demonstrates the pattern (`base_router.py:101–135`). It accepts a raw CQL2-JSON body and feeds it to `cql_post_parser_dependency` (`dependencies.py:213–228`). The rest of the listing pipeline (`listing_function`) is identical to the GET path. This confirms the approach is sound.

### Browser and Proxy Compatibility

Some enterprise firewalls and reverse proxies strip or reject long query strings but pass POST bodies through unchanged. Supporting POST makes Prez usable in restricted enterprise deployments.

### Client Ergonomics

Constructing a JSON body is often cleaner than URL-encoding for programmatic clients, especially when the filter is already a Python/JavaScript dict.

---

## 2. Proposed POST Interface

### Design: All Params in JSON Body

For every listing endpoint, `POST` accepts `Content-Type: application/json` with a body containing the same parameter names used in GET query strings:

```json
{
  "_mediatype": "text/turtle",
  "_profile": "https://example.org/profile",
  "page": 1,
  "limit": 10,
  "q": "search term",
  "filter": { "op": "s_intersects", "args": [ { "property": "geometry" }, { "type": "Point", "coordinates": [153.0, -27.5] } ] },
  "filter-lang": "cql2-json",
  "filter_crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
  "bbox": [153.0, -28.0, 154.0, -27.0],
  "datetime": "2020-01-01T00:00:00Z/2021-01-01T00:00:00Z",
  "order_by": "label",
  "order_by_direction": "ASC",
  "offset": null,
  "startindex": null
}
```

All fields are optional; defaults match the GET defaults defined in `ListingQueryParams` (`models/query_params.py:127–248`).

Note the field name `filter-lang` (hyphenated) to match the GET alias `filter-lang` used in `ListingQueryParams.__init__`.

### Backward Compatibility

- All existing GET endpoints remain unchanged.
- `POST /cql` (raw CQL2-JSON body) remains unchanged and is **not** replaced or altered.
- New POST variants are purely additive.

### Body vs. Query Param Mixing

URL query params are **not** merged with the JSON body in POST requests. The body is the single source of truth for a POST call. Merging would create ambiguous semantics (which takes precedence? how are conflicts resolved?). Clients that need query params should use GET.

---

## 3. Affected Endpoints

| Endpoint | Current Methods | After |
|---|---|---|
| `GET /search` | GET | + `POST /search` |
| `GET /cql` | GET | unchanged |
| `POST /cql` (raw CQL body) | POST | unchanged (kept for compatibility) |
| `GET /profiles` | GET | + `POST /profiles` |
| `GET /concept-hierarchy/{curie}/top-concepts` | GET | + `POST /concept-hierarchy/{curie}/top-concepts` |
| `GET /concept-hierarchy/{curie}/narrowers` | GET | + `POST /concept-hierarchy/{curie}/narrowers` |
| `GET /object` | GET | + `POST /object` |
| Dynamic/custom endpoints (`custom_endpoints.py`) | GET only (`methods=["GET"]` at line 166) | + POST |
| OGC Features endpoints | GET/HEAD/OPTIONS | **excluded** (OGC API spec-constrained) |
| `/sparql` | GET + POST | unchanged |

---

## 4. Issues and Considerations

### 4.1 HTTP Semantics / REST Conventions

These POST endpoints are **reads** — they are safe and idempotent in practice, but HTTP POST is formally neither safe nor idempotent per RFC 9110. This is a known, acceptable deviation. It is a well-established pattern:

- Elasticsearch `POST /_search`
- SPARQL 1.1 Protocol POST query form
- OGC API — Features Part 3 (CQL2) POST filter

Document this explicitly in the API description: "POST on listing endpoints is a read operation. The HTTP method is POST solely to allow large request payloads; the server does not create or modify any resource."

An alternative — GET with a body — is technically permitted by RFC 9110 §9.3.1 but is widely unsupported by HTTP clients and libraries (curl ignores it, many proxies strip it). POST is the pragmatic choice.

### 4.2 HTTP Caching

GET responses can be cached by CDNs, reverse proxies (Nginx, Traefik, Varnish), and browsers. POST responses are generally not cached at the HTTP level.

**Trade-off:** Users choosing POST for large payloads are unlikely to rely on HTTP-level caching. They are typically programmatic clients with application-level caching. This trade-off is acceptable, but should be documented so operators are aware.

### 4.3 CORS

POST with `Content-Type: application/json` triggers a CORS preflight (`OPTIONS`) request. Prez's CORS middleware already includes `POST` in `Access-Control-Allow-Methods`.

**Action required:** Verify that `Content-Type` (and `Authorization` / `subscription-key` if used) is listed in `Access-Control-Allow-Headers`. The `application/json` content type alone is what upgrades the request from "simple" to "preflighted" per the CORS spec.

### 4.4 Content-Type Enforcement

POST endpoints must:

1. Require `Content-Type: application/json`. Respond with `HTTP 415 Unsupported Media Type` if the content type is missing or incorrect.
2. Respond with `HTTP 400 Bad Request` for unparseable JSON bodies.
3. Respond with `HTTP 400 Bad Request` for invalid field values (e.g., non-integer `page`, invalid `filter-lang` enum value).

Clear error messages are essential since POST body errors are harder to debug than query string errors.

The `cql_post_parser_dependency` at `dependencies.py:213–228` is the template:

```python
async def cql_post_parser_dependency(request: Request, ...) -> CQLParser:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")
    ...
```

A `listing_post_params_dependency` should follow the same pattern, parsing the body into a `ListingQueryParams`-equivalent object.

### 4.5 OpenAPI Documentation

FastAPI auto-generates OpenAPI schemas from Pydantic `BaseModel` request bodies. However, `ListingQueryParams` is implemented as a plain Python class (not a Pydantic `BaseModel`) because Pydantic cannot pass field descriptions through to OpenAPI docs when used as query params (see comment at `models/query_params.py:128–133`).

For POST body documentation, a Pydantic `BaseModel` works correctly. A new `ListingPostBody(BaseModel)` class should be created, mirroring all fields of `ListingQueryParams` with the same defaults and descriptions, used solely for the POST body schema.

This gives clean OpenAPI docs for POST without changing the GET dependency chain.

### 4.6 Dynamic Endpoints (`custom_endpoints.py`)

Dynamic route registration at `custom_endpoints.py:162–169` is hardcoded to `methods=["GET"]`. To add POST support:

**Implementation uses Option B:** Register two separate route handlers — one GET and one POST — each with their own handler function. The GET handler uses `ListingQueryParams = Depends()` (query string); the POST handler uses `listing_post_params_dependency` (JSON body). This avoids method-detection branching and keeps the GET and POST paths cleanly separated.

### 4.7 Breaking Change: `/cql` POST Format

**This is a breaking change.**

`POST /cql` previously accepted a raw CQL2-JSON body (the filter expression itself, not wrapped):

```json
{ "op": "s_intersects", "args": [...] }
```

After this change, `POST /cql` uses the same wrapped format as all other listing POST endpoints:

```json
{
  "filter": { "op": "s_intersects", "args": [...] },
  "page": 1,
  "limit": 10,
  "_mediatype": "text/turtle"
}
```

**Rationale:** Consistency is more valuable than backward compatibility for an endpoint that was never formally released or documented as stable. Using different body shapes for `/cql` POST vs. other POST endpoints creates permanent confusion. The wrapped format also allows clients to pass pagination and mediatype params in the same request body as the filter.

**Migration:** Clients using the old raw body format must wrap the CQL expression in `{"filter": {...}}`. The `filter` key is required on `POST /cql`; omitting it returns HTTP 400.

### 4.8 Large Body Limits

FastAPI/Starlette has no default request body size limit. Production deployments behind Nginx or Traefik may impose limits (Nginx default: 1 MB; Traefik: no default limit).

**Recommended proxy config documentation:**

```nginx
# Nginx — increase client_max_body_size if CQL filters are large
client_max_body_size 10m;
```

For most use cases, CQL filters will not exceed a few KB. The limit primarily matters for bulk or automated workflows.

---

## 5. Implementation Sketch

This section is a reference for implementers. **No code changes are in scope for this document.**

### Key Files to Change

| File | Change |
|---|---|
| `prez/dependencies.py` | Update `cql_post_parser_dependency` to wrapped format; add `listing_post_params_dependency`, `get_negotiated_pmts_post`, `get_endpoint_structure_post`, `get_profile_nodeshape_post`, `generate_search_query_post`, `cql_post_listing_parser_dependency`; add object POST variants |
| `prez/models/query_params.py` | Add `ListingPostBody(BaseModel)` Pydantic model with all `ListingQueryParams` fields, for OpenAPI schema |
| `prez/routers/base_router.py` | Add `@router.post()` handlers for `/search`, `/profiles`, `/concept-hierarchy/{curie}/top-concepts`, `/concept-hierarchy/{curie}/narrowers`, `/object`; update `POST /cql` |
| `prez/routers/custom_endpoints.py` | Register a second POST route alongside each GET listing route (Option B) |

### `listing_post_params_dependency` Skeleton

```python
async def listing_post_params_dependency(
    request: Request,
) -> ListingQueryParams:
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    if body is None:
        body = {}
    # Map body fields to ListingQueryParams constructor args
    # Apply same validation as ListingQueryParams.__init__
    ...
```

### POST Route Registration Pattern

```python
@router.post(
    path="/search",
    summary="Search (POST)",
    name=OGCE["search-post"],
    responses=responses,
)
async def listings_post(
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),
    endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    ...
):
    return await listing_function(...)
```

Note: `cql_post_parser_dependency` is updated to the wrapped format (reading `body["filter"]`). For the new general listing POST endpoints, a separate `cql_post_listing_parser_dependency` handles optional CQL (no filter → returns `None`). The POST listing handler also uses `get_negotiated_pmts_post`, `get_endpoint_structure_post`, `get_profile_nodeshape_post`, and `generate_search_query_post` — POST-specific variants of the GET dependency chain that read params from `listing_post_params_dependency` instead of `request.query_params`.

---

## 6. Testing Strategy

### 6.1 GET/POST Parity Tests

For every POST endpoint, write a paired GET test with equivalent params and assert the responses are identical (same body, same HTTP status, same `Content-Type`). This is the primary validation of correctness.

Example pattern:

```python
@pytest.mark.parametrize("endpoint", ["/search", "/profiles"])
def test_get_post_parity(client, endpoint, cql_filter_fixture):
    get_response = client.get(
        endpoint,
        params={"filter": json.dumps(cql_filter_fixture), "limit": 10}
    )
    post_response = client.post(
        endpoint,
        json={"filter": cql_filter_fixture, "limit": 10},
    )
    assert get_response.status_code == post_response.status_code
    assert get_response.content == post_response.content
    assert get_response.headers["content-type"] == post_response.headers["content-type"]
```

### 6.2 Unit Tests: `listing_post_params_dependency`

New file: `tests/test_listing_post_params.py`

Cover:

| Test case | Expected result |
|---|---|
| Valid body with all fields | Correct `ListingQueryParams` attributes |
| Empty body `{}` | All defaults applied |
| Missing `Content-Type` | HTTP 415 |
| Wrong `Content-Type: text/plain` | HTTP 415 |
| Malformed JSON body | HTTP 400 |
| Invalid `page` value (e.g., `0`, `"abc"`) | HTTP 400 |
| Invalid `filter-lang` enum value | HTTP 400 |
| Conflicting pagination params (`page` + `offset`) | HTTP 400 (matches `validate_pagination_params`) |
| Invalid `filter` JSON (not a dict) | HTTP 400 |
| `bbox` with wrong number of coordinates | HTTP 400 |

### 6.3 Integration Tests

New file: `tests/test_post_listings.py`

- Parametrized across `/search`, `/profiles`, `/concept-hierarchy/{curie}/top-concepts`, `/concept-hierarchy/{curie}/narrowers`, `/object`, and at least one custom endpoint.
- Reuse existing CQL filter fixtures from `tests/test_cql.py`. Send via POST body `{"filter": {...}}` and compare to GET `?filter=<url-encoded-json>`.
- Test a large CQL payload (> 4 KB) that would fail or be unwieldy as a GET query string. Assert HTTP 200 and valid response body.
- Test `bbox` in POST body.
- Test `datetime` in POST body (interval format: `"2020-01-01T00:00:00Z/2021-01-01T00:00:00Z"`).
- Test `_mediatype` in POST body returns the correct content type.

### 6.4 Regression

All existing GET tests must continue to pass unchanged. The POST implementation must not modify any GET-path code.

### 6.5 Updated CQL POST Tests

`tests/test_cql.py` contains two previously disabled tests:

```python
# test_simple_post (line 34)
# test_intersects_post (line 53)
```

These are uncommented and updated to use the **new wrapped format** `{"filter": cql_json}` since `POST /cql` now requires the filter to be under the `filter` key. The old raw-body format is gone.

### 6.6 CORS Preflight Test

```python
def test_post_cors_preflight(client):
    response = client.options(
        "/search",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
```

### 6.7 Excluded Endpoints

OGC Features endpoints are constrained to GET/HEAD/OPTIONS by the OGC API — Features specification. Do not add POST there. Tests must verify that `POST` on OGC Features paths returns HTTP 405.

---

## 7. Summary

| Area | Decision |
|---|---|
| Body format | JSON body, same param names as GET query params |
| `POST /cql` compat | **Breaking change** — now uses wrapped `{"filter": {...}}` format |
| Param mixing (body + query string) | Not supported — body is sole source of truth for POST |
| HTTP semantics | Documented as safe read operation using POST for payload size only |
| Caching | HTTP caching lost for POST; acceptable trade-off |
| CORS | Verify `Content-Type` in `Access-Control-Allow-Headers` |
| Content-Type | Enforce `application/json`; return 415 otherwise |
| OpenAPI | New `ListingPostBody(BaseModel)` for clean POST schema |
| Dynamic endpoints | Register separate POST route per custom endpoint |
| OGC Features | Excluded |
| Testing | GET/POST parity tests as primary correctness check |
