Results are counted in the following way:

Scenario:
There are 132 total items.

`LISTING_COUNT_LIMIT = 100`

---

## Configuration Options

### `LISTING_COUNT_ON_DEMAND`

Controls when count queries are executed for listing endpoints. This provides performance optimization by allowing clients to explicitly request counts only when needed.

- **Default**: `false` (for backwards compatibility)
- **Future versions**: May default to `true`

**When `LISTING_COUNT_ON_DEMAND=false` (default):**
- Counts are automatically included in RDF listing responses (up to `LISTING_COUNT_LIMIT`)
- This is the current/legacy behaviour

**When `LISTING_COUNT_ON_DEMAND=true`:**
- Counts are NOT included in regular RDF listing responses
- To get the count, clients must pass `?resultType=hits`
- When `resultType=hits` is passed, ONLY the count is returned (no items/data)
- This matches the behaviour already implemented for OGC Features endpoints
- Provides finer control for frontends over when expensive count queries are performed

**Note:** GeoJSON responses always follow the hits-only pattern (counts only with `?resultType=hits`) regardless of this setting.

### Behaviour Matrix

| MediaType | LISTING_COUNT_ON_DEMAND | Request Type | Response Contains |
|-----------|------------------------|--------------|-------------------|
| Annotated RDF (e.g., `text/anot+turtle`) | `false` (default) | Normal listing | Items + Count |
| Non-annotated RDF (e.g., `text/turtle`) | `false` (default) | Normal listing | Items only (no count*) |
| RDF (annotated or non-annotated) | `false` (default) | `?resultType=hits` | Count only (no items) |
| RDF (annotated or non-annotated) | `true` | Normal listing | Items only (no count) |
| RDF (annotated or non-annotated) | `true` | `?resultType=hits` | Count only (no items) |
| GeoJSON | `false` or `true` | Normal listing | Features only (no `numberMatched`**) |
| GeoJSON | `false` or `true` | `?resultType=hits` | `numberMatched` only (no features) |

*Counts are annotations, so non-annotated mediatypes never include counts in normal listings (only with `?resultType=hits`).

**`numberMatched` may be inferred on the first page if the number of features returned is less than the page limit, but no count query is executed.

---

**Future Changes:** In a future major release, the `LISTING_COUNT_ON_DEMAND` setting will be removed and the behaviour will default to the current `LISTING_COUNT_ON_DEMAND=true` behaviour (counts only returned when explicitly requested via `?resultType=hits`).

---

## Listing Endpoints (Non-Search)

| Page | Page Size | Start Item | End Item | Total Count Displayed |
|------|-----------|------------|----------|------------------------|
| 1    | 20        | 1          | 20       | >100                   |
| 2    | 20        | 21         | 40       | >100                   |
| 5    | 20        | 81         | 100      | >100                   |
| 6    | 20        | 101        | 120      | >120                   |
| 7    | 20        | 121        | 132      | 132                    |

---

## Search Endpoints (`SEARCH_USES_LISTING_COUNT_LIMIT = false`)  
_Count query not run — uses `page size + 1` fetch logic to determine if more results exist._

| Page | Page Size | Start Item | End Item | Total Count Displayed |
|------|-----------|------------|----------|------------------------|
| 1    | 25        | 1          | 26       | >25                    |
| 2    | 25        | 26         | 51       | >50                    |
| 5    | 25        | 101        | 126      | >125                   |
| 6    | 25        | 126        | 132      | 132                    |

---

## Search Endpoints (`SEARCH_USES_LISTING_COUNT_LIMIT = true`)  
_Count query is run. The same `LISTING_COUNT_LIMIT` is enforced._

| Page | Page Size | Start Item | End Item | Total Count Displayed |
|------|-----------|------------|----------|------------------------|
| 1    | 20        | 1          | 21       | >100                   |
| 3    | 20        | 41         | 61       | >100                   |
| 5    | 20        | 81         | 101      | >100                   |
| 6    | 20        | 101        | 121      | >120                   |
| 7    | 20        | 121        | 132      | 132                    |