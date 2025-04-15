# Path Aliases

## Introduction

Prez utilizes SHACL shapes to define how data should be selected and structured for API responses. SHACL property paths (`sh:path`) can become complex, involving sequences, alternatives, or inverse paths. The Path Alias feature allows you to define a simple, custom URI (an "alias") to represent these potentially complex paths in the output RDF graph.

## Motivation

-   **Simplified Output:** Instead of returning data structured according to a complex, nested property path, using an alias presents the data as if it were connected to the main resource via a single, direct predicate (the alias). This can significantly simplify the RDF graph returned by the API.
-   **Client Compatibility:** Some client applications may have difficulty parsing or interpreting complex SPARQL property paths. Aliases provide a simpler, predicate-object structure that is easier to consume.
-   **Stable Predicates:** While the underlying data structure or the SHACL path to reach it might evolve, an alias can provide a stable predicate URI in the API response, decoupling the client from the intricacies of the data model's path structure.

## Syntax

Path aliases are defined using the `shext:pathAlias` predicate (you'll need to define a suitable prefix like `shext:` for a namespace like `http://example.com/shacl-extension#` or your own).

There are two main ways to apply an alias:

1.  **On the Property Shape BNode:**
    Define `shext:pathAlias` directly within the `sh:property` blank node. This alias applies to the `sh:path` defined in the *same* blank node.

    ```turtle
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX shext: <http://example.com/shacl-extension#>

    <http://example-profile>
        a sh:NodeShape ;
        sh:property [
            # Simple Path Example
            sh:path dcterms:title ;
            shext:pathAlias <https://alias/title> ;
        ] ,
        [
            # Sequence Path Example
            sh:path ( prov:qualifiedDerivation prov:hadRole ) ;
            shext:pathAlias <https://alias/derivation-role> ;
        ] .

    ```

2.  **Adjacent to Nested `sh:path` (within `sh:union`, `sh:alternativePath`, etc.):**
    When using constructs like `sh:union` or `sh:alternativePath` that contain lists of paths, you can define an alias specifically for one or more of those nested paths. The alias is placed within the blank node that *also* contains the nested `sh:path`.

    ```turtle
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX shext: <http://example.com/shacl-extension#>

    <http://example-profile>
        a sh:NodeShape ;
        sh:property [
            sh:path [
                sh:union (
                    # Path 1: No alias
                    skos:prefLabel

                    # Path 2: Has an alias defined adjacent to its sh:path
                    [
                        sh:path ( prov:qualifiedDerivation prov:hadRole ) ;
                        shext:pathAlias <https://alias/derivation-role> ;
                    ]
                )
            ]
        ] .
    ```

## Behavior: `CONSTRUCT` vs `WHERE`

The key aspect of path aliasing is how it affects the generated SPARQL query:

-   **`WHERE` Clause:** The *original*, potentially complex `sh:path` (e.g., `dcterms:title`, `( prov:qualifiedDerivation prov:hadRole )`, `skos:prefLabel|rdfs:label`) is **always** used in the `WHERE` clause to locate and filter the data in the underlying triplestore.
-   **`CONSTRUCT` Clause:**
    -   If `use_path_aliases` is `True` (see Configuration below) and a `shext:pathAlias` is defined for a path, the **alias URI** is used as the predicate in the `CONSTRUCT` clause.
    -   If `use_path_aliases` is `False`, or if no alias is defined for a path, the *original* path structure is replicated in the `CONSTRUCT` clause.

**Example:**

Given this shape with an alias:

```turtle
[
    sh:path dcterms:title ;
    shext:pathAlias <https://alias/title> ;
]
```

-   **`WHERE` clause will contain:** `?focus_node dcterms:title ?value .`
-   **`CONSTRUCT` clause (if `use_path_aliases = True`) will contain:** `?focus_node <https://alias/title> ?value .`
-   **`CONSTRUCT` clause (if `use_path_aliases = False`) will contain:** `?focus_node dcterms:title ?value .`

For a sequence path like `( prov:qualifiedDerivation prov:hadRole )` aliased to `<https://alias/derivation-role>`:

-   **`WHERE` clause will contain:** `?focus_node prov:qualifiedDerivation ?intermediate . ?intermediate prov:hadRole ?value .`
-   **`CONSTRUCT` clause (if `use_path_aliases = True`) will contain:** `?focus_node <https://alias/derivation-role> ?value .`
-   **`CONSTRUCT` clause (if `use_path_aliases = False`) will contain:** `?focus_node prov:qualifiedDerivation ?intermediate . ?intermediate prov:hadRole ?value .`

## Configuration

The use of path aliases in the `CONSTRUCT` clause is controlled by a setting, typically found in `prez.config.settings`:

-   `use_path_aliases = True`: Enables the use of defined aliases in the `CONSTRUCT` clause.
-   `use_path_aliases = False`: Disables aliases; the original paths are used in the `CONSTRUCT` clause.

This allows administrators to choose whether they want the simplified output structure provided by aliases or the structure that directly mirrors the SHACL paths.
