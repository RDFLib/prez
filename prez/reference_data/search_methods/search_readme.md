## General info

Search results are returned according to profiles. As such, profiles can be used to determine which properties,
inbound/outbound links etc. are returned for a search result.

## Adding search methods
Search methods can be added in two different ways to Prez:

1. Adding turtle files to the `prez/reference_data/search_methods` directory in the `prez` project. Prez will load these
files on application startup.
2. Adding remote search methods to a graph in Prez's backend. Prez will load these search methods on application
startup, by looking within the `prez:systemGraph` graph, for instances of `prez:SearchMethod`.
TODO: provide an update endpoint for adding search methods to the search methods dictionary - allowing instance data to
be kept separate from system methods.

## Defining search methods
- Search methods must be RDF. They must be in turtle if added to the `prez/reference_data/search_methods` directory.
- Declare a class of `prez:SearchMethod`
- Have the following predicates, with objects as described:
  - `dcterms:identifier` - a unique identifier for the search method used in the query string argument.
  - `rdfs:label` - a name for the search method.
  - `rdf:value` - a SPARQL SELECT query in the form described below:

### SPARQL SELECT query format
Search SPARQL queries MUST:

- **use fully qualified URIs (i.e. no namespace prefixes are allowed). This is because simple string concatenation is used to insert the search query as a subquery in a query which gathers additional context for search results.**
- return search results bound to the `?search_result_uri` variable. This is because the search method is used as a
sub-select in an object listing query which expects this variable.
- accept a search term using `$TERM` in the query. This will be substituted for the search term provided by the user.


Search SPARQL queries SHOULD:

- include a LIMIT clause by including `$LIMIT` to limit the number of results returned. Prez will default this limit to
20 results if a LIMIT is not specified by users.

Search SPARQL queries MAY:

- return search results with the following variables bound:
  - `?weight` - a float value representing the weight of the search result; with higher values being more relevant
  - `?predicate` - the predicate (of the triple) the search result was found on. (Full text search can search across multiple predicates in
  a group. This variable can be used to distinguish which predicate the search result was found on.)
  - `?match` The (full) literal value of the object for the search result.

Example query snippet:

```sparql
SELECT DISTINCT ?search_result_uri ?predicate ?match
   WHERE { ?search_result_uri ?predicate ?match .
        FILTER REGEX(?match, "^$TERM$$", "i")
            }
        } LIMIT $LIMIT
```
