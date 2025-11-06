# Lucene Full-Text Search Escaping Design

## Overview

Prez exposes Apache Jena Fuseki's Lucene-based full-text search (FTS) capabilities through its API. This document describes the escaping strategy used to handle special characters in search queries that pass through two layers: Lucene query syntax and SPARQL query syntax.

## Design Principles

### 1. Lucene Syntax Exposure

The API accepts search strings that may contain **Lucene query syntax**, allowing clients to leverage full-text search features including:

- **Wildcards**: `*` (multiple characters), `?` (single character)
- **Range queries**: `[a TO z]`, `{1 TO 10}`
- **Boolean operators**: `AND`, `OR`, `NOT`, `+`, `-`
- **Phrase matching**: `"exact phrase"`
- **Grouping**: `(term1 OR term2)`
- **Fuzzy search**: `~`
- **Proximity search**: `"word1 word2"~10`
- **Boosting**: `term^2`

This design exposes FTS functionality directly to front-end applications, enabling sophisticated search experiences.

### 2. Client-Side Escaping Requirement

If a client wants to search for a **literal special character** (rather than using its Lucene function), they must escape it with a backslash (`\`) according to Lucene escaping rules.

**Lucene special characters that require escaping:**
```
+ - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
```

**Example:**
- To search for the literal string `C++`, the client must send: `C\+\+`
- To search for `file.txt`, the client must send: `file.txt` (period doesn't need escaping)
- To search for `2:1 ratio`, the client must send: `2\:1 ratio`

### 3. Server-Side SPARQL Escaping

The backend receives the client's search string (which may contain Lucene syntax and/or Lucene escape sequences) and must prepare it for inclusion in a SPARQL query. This requires two escape operations:

#### a. Escape the Escape Character

Any backslashes (`\`) used by the client for Lucene escaping must themselves be escaped for SPARQL:

```python
term = term.replace("\\", "\\\\")
```

**Why:** In SPARQL string literals, backslash is an escape character. A single `\` would be interpreted by SPARQL, potentially corrupting the Lucene query. By doubling it (`\\`), SPARQL interprets it as a literal backslash, which is then passed correctly to Lucene.

#### b. Escape Double Quotes

Double quotes (`"`) are special in both Lucene (for phrase matching) and SPARQL (for string literal delimiters):

```python
term = term.replace('"', '\\"')
```

**Why:** The search term is embedded within a SPARQL string literal (delimited by `"`). Any unescaped `"` within the term would prematurely close the string literal, causing a syntax error. Escaping it as `\"` ensures SPARQL treats it as part of the string content, allowing Lucene to receive and interpret it as a phrase delimiter.

## Implementation

The escaping logic is implemented in `prez/services/query_generation/search_fuseki_fts.py`:

```python
# Line 133-134
term = term.replace("\\", "\\\\")  # escape for SPARQL anything that has been Lucene escaped already
term = term.replace('"', '\\"')     # escape quotes for SPARQL
```

**Important:** The order of operations matters. Backslashes must be escaped first to avoid double-escaping the backslashes introduced when escaping quotes.

## Examples

### Example 1: Wildcard Search
- **Client sends:** `test*`
- **After escaping:** `test*` (no change, `*` is not escaped for SPARQL)
- **Lucene receives:** `test*` (wildcard search for terms starting with "test")

### Example 2: Exact Phrase Search
- **Client sends:** `"hello world"`
- **After escaping:** `\"hello world\"` (quotes escaped for SPARQL)
- **Lucene receives:** `"hello world"` (exact phrase match)

### Example 3: Literal Plus Sign
- **Client sends:** `C\+\+` (escaping `+` for Lucene)
- **After escaping:** `C\\+\\+` (backslashes doubled for SPARQL)
- **Lucene receives:** `C\+\+` (searches for literal "C++")

### Example 4: Complex Query with Multiple Features
- **Client sends:** `name:"John Doe" AND age:[25 TO 35]`
- **After escaping:** `name:\"John Doe\" AND age:[25 TO 35]`
- **Lucene receives:** `name:"John Doe" AND age:[25 TO 35]` (boolean query with phrase and range)

### Example 5: Literal Backslash
- **Client sends:** `path\:C\:\\Users` (escaping `:` and `\` for Lucene)
- **After escaping:** `path\\:C\\:\\\\Users` (all backslashes doubled)
- **Lucene receives:** `path\:C\:\Users` (searches for literal "path:C:\Users")

## Security Considerations

This escaping strategy prevents SPARQL injection attacks by ensuring that:
1. All user input is properly escaped for the SPARQL context
2. No user input can break out of the string literal containing the search term
3. The integrity of the generated SPARQL query is maintained

The Lucene query parser itself handles its own input validation and prevents malformed queries from executing.

## Summary

| Layer | Special Character Handling | Responsibility |
|-------|---------------------------|----------------|
| **Client (Lucene)** | Must escape literal special characters with `\` | Front-end developer |
| **Server (SPARQL)** | Must escape `\` as `\\` and `"` as `\"` | Backend (automated) |
| **Fuseki/Lucene** | Parses escaped Lucene query syntax | Jena Fuseki |

This two-layer escaping strategy allows full Lucene query syntax support while maintaining SPARQL query integrity and security.
