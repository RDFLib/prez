Results are counted in the following way:

Scenario:
There are 132 total items.

`LISTING_COUNT_LIMIT = 100`

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