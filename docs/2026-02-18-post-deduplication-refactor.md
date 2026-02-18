# Deduplication Refactor: Unifying GET and POST Dependency Chains

**Date:** 2026-02-18
**Context:** Follow-up to `2026-02-18-post-support-all-endpoints.md`

---

## Problem

The current POST implementation (Option 1) introduced POST-specific variants of several dependency functions because each existing function reads params from `request.query_params` directly — something that doesn't work for POST requests where params come from the JSON body. The result is mirrored function pairs:

| GET version | POST version | Root cause |
|---|---|---|
| `generate_search_query` | `generate_search_query_post` | Reads `request.query_params` directly |
| `get_negotiated_pmts` | `get_negotiated_pmts_listing_post` + `get_negotiated_pmts_post_object` | Passes `request.query_params` to `NegotiatedPMTs` |
| `get_endpoint_structure` | `get_endpoint_structure_listing_post` + `get_endpoint_structure_post_object` | Depends on a specific pmts variant |
| `get_profile_nodeshape` | `get_profile_nodeshape_listing_post` + `get_profile_nodeshape_post_object` | Reads `request.query_params.get("iri")` and depends on a specific pmts variant |

The logic in each pair is identical. Only the *source* of params differs.

---

## Root Cause

Three specific lines drive all the duplication:

**1. `generate_search_query` (`dependencies.py:771–812`):**
```python
term = request.query_params.get("q")
if params.get("facet_profile"): ...  # params = request.query_params
predicates = request.query_params.getlist("predicates")
page = request.query_params.get("page", 1)
limit = request.query_params.get("limit")
```

**2. `get_negotiated_pmts` (`dependencies.py:1107–1109`):**
```python
pmts = NegotiatedPMTs(
    params=request.query_params,   # ← this line
    ...
)
```

**3. `get_profile_nodeshape` (`dependencies.py:1144–1146`):**
```python
identifier_value = request.query_params.get("iri") or request.query_params.get("uri")
```

All three read directly from `request.query_params` instead of from a `ListingQueryParams` object that already holds the parsed, validated params.

---

## Refactor Plan (Option 3)

### Step 1: Add `predicates` to `ListingQueryParams`

`generate_search_query` reads `request.query_params.getlist("predicates")` — a field not currently in `ListingQueryParams`. Add it so the full search context is captured in the query params object.

**File:** `prez/models/query_params.py`

```python
class ListingQueryParams:
    def __init__(
        self,
        ...
        predicates: List[str] = Query(default=[], description="Search predicates"),
        ...
    ):
        ...
        self.predicates = predicates
```

And add `predicates` to `ListingPostBody` model. For the POST body, `predicates` would be a list field: `"predicates": ["http://..."]`.

---

### Step 2: Extract `generate_search_query` logic to a shared implementation

**File:** `prez/dependencies.py`

Extract the body of `generate_search_query` into a private coroutine that accepts `ListingQueryParams` directly:

```python
async def _generate_search_query_impl(
    query_params: ListingQueryParams,
    system_repo: Repo,
    endpoint_uri_type: tuple,
):
    """Shared search query generation logic. Works for both GET and POST."""
    term = query_params.q

    def has_filtering_params() -> bool:
        return bool(
            query_params.facet_profile
            or query_params._filter
            or query_params.bbox
            or query_params.datetime
        )

    if not term:
        if endpoint_uri_type[0] == EP["extended-ogc-records/search"]:
            if has_filtering_params():
                return DummySearchMarker()
            raise HTTPException(status_code=400, detail="...")
        return None

    predicates = query_params.predicates or []
    page = query_params.page or 1
    limit = query_params.limit or settings.search_count_limit
    offset = limit * (page - 1)
    # ... rest of FTS/DEFAULT logic unchanged ...
```

Then the two thin wrappers become:

```python
async def generate_search_query(
    query_params: ListingQueryParams = Depends(),            # GET: from query string
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: tuple = Depends(get_endpoint_uri_type),
):
    return await _generate_search_query_impl(query_params, system_repo, endpoint_uri_type)


async def generate_search_query_post(
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),  # POST: from body
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: tuple = Depends(get_endpoint_uri_type),
):
    return await _generate_search_query_impl(query_params, system_repo, endpoint_uri_type)
```

The actual logic lives in exactly one place. Removing `request: Request` from `generate_search_query`'s signature is a bonus simplification.

---

### Step 3: Extract `get_negotiated_pmts` logic to a shared implementation

**File:** `prez/dependencies.py`

```python
async def _negotiate_pmts(
    *,
    request: Request,
    params_dict: dict,           # {"_profile": ..., "_mediatype": ...}
    klasses: list,
    listing: bool,
    system_repo: Repo,
    url_path: str,
) -> NegotiatedPMTs:
    """Shared PMTS negotiation. Decoupled from param source (GET vs POST)."""
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=params_dict,
        classes=klasses,
        listing=listing,
        system_repo=system_repo,
        current_path=url_path,
    )
    await pmts.setup()
    return pmts
```

Then the three variants become thin wrappers that assemble `params_dict` from their respective source:

```python
# GET (existing, refactored)
async def get_negotiated_pmts(request: Request, ...):
    params_dict = {
        "_profile": request.query_params.get("_profile", ""),
        "_mediatype": request.query_params.get("_mediatype", ""),
    }
    ...
    return await _negotiate_pmts(params_dict=params_dict, ...)


# POST listing (new, refactored)
async def get_negotiated_pmts_listing_post(
    query_params: ListingQueryParams = Depends(listing_post_params_dependency), ...
):
    params_dict = {"_profile": query_params.profile or "", "_mediatype": query_params.mediatype or ""}
    ...
    return await _negotiate_pmts(params_dict=params_dict, ...)


# POST /object (new, refactored)
async def get_negotiated_pmts_post_object(
    body: dict = Depends(object_post_params_dependency), ...
):
    params_dict = {"_profile": body.get("_profile", ""), "_mediatype": body.get("_mediatype", "")}
    ...
    return await _negotiate_pmts(params_dict=params_dict, ...)
```

---

### Step 4: Extract `get_endpoint_structure` and `get_profile_nodeshape` logic

These depend on pmts variants but otherwise contain the same logic. Extract shared implementations:

```python
def _compute_endpoint_structure(pmts: NegotiatedPMTs, endpoint_uri: URIRef) -> tuple:
    if (endpoint_uri in settings.system_endpoints) or (
        pmts.selected.get("profile") == ALTREXT["alt-profile"]
    ):
        return ("profiles",)
    return settings.endpoint_structure


def _build_profile_nodeshape(pmts: NegotiatedPMTs, focus_node) -> NodeShape:
    return NodeShape(
        uri=pmts.selected.get("profile"),
        graph=profiles_graph_cache,
        kind="profile",
        focus_node=focus_node,
    )
```

Then `get_endpoint_structure`, `get_endpoint_structure_listing_post`, and `get_endpoint_structure_post_object` each call `_compute_endpoint_structure(pmts, endpoint_uri)`. Similarly for `get_profile_nodeshape` variants.

The GET/POST split in the dep function signatures is unavoidable (FastAPI needs separate functions to use different `pmts` dependencies), but the *logic* is no longer duplicated.

---

## End State After Refactor

The dependency chain structure remains the same — there are still separate GET and POST dep function names. But all computation logic lives in private `_impl` functions:

```
_generate_search_query_impl    ← shared logic
    generate_search_query          (GET wrapper)
    generate_search_query_post     (POST wrapper)

_negotiate_pmts                ← shared logic
    get_negotiated_pmts            (GET wrapper)
    get_negotiated_pmts_listing_post  (POST listing wrapper)
    get_negotiated_pmts_post_object   (POST /object wrapper)

_compute_endpoint_structure    ← shared logic (pure function)
    get_endpoint_structure         (GET wrapper)
    get_endpoint_structure_listing_post
    get_endpoint_structure_post_object

_build_profile_nodeshape       ← shared logic (pure function)
    get_profile_nodeshape          (GET wrapper)
    get_profile_nodeshape_listing_post
    get_profile_nodeshape_post_object
```

The wrappers are then trivial — typically 3–5 lines each. The test surface stays the same (test the `_impl` functions directly for logic, test the wrappers only for wiring).

---

## Why the Wrappers Can't Be Eliminated

FastAPI's `Depends()` mechanism selects the source function by function object identity. There is no way to tell FastAPI "use this dependency function for GET, that one for POST" within a single handler — the handler must explicitly declare which dep function to use. Therefore:

- GET handlers declare `Depends(generate_search_query)` (reads from query string)
- POST handlers declare `Depends(generate_search_query_post)` (reads from body)

These function names cannot be merged. What CAN be merged is the logic inside them.

---

## Additional Gap: `predicates` in POST

The current POST implementation silently ignores the `predicates` search parameter (FTS predicate filtering), which GET supports via `request.query_params.getlist("predicates")`. Step 1 above (adding `predicates` to `ListingQueryParams`) fixes this gap. The POST body would support:

```json
{ "q": "basin", "predicates": ["http://www.w3.org/2004/02/skos/core#prefLabel"] }
```

---

## Files to Change

| File | Changes |
|---|---|
| `prez/models/query_params.py` | Add `predicates: List[str]` to `ListingQueryParams`; add to `ListingPostBody` |
| `prez/dependencies.py` | Extract `_generate_search_query_impl`, `_negotiate_pmts`, `_compute_endpoint_structure`, `_build_profile_nodeshape`; refactor existing functions to call them |

No router changes needed. No test changes needed (existing tests cover the wrappers; add unit tests for `_impl` functions directly).
