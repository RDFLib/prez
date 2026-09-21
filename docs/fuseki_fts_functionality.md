# Fuseki FTS (Full-Text Search) Integration

Prez integrates with Apache Jena Fuseki's full-text search capabilities to enable efficient text search across RDF data.

## Basic Usage

Use the `predicates` URL query parameter to specify which indexed properties or property shapes to search:

```
/search?q=geological&predicates=http://www.w3.org/2000/01/rdf-schema#label,http://www.w3.org/2004/02/skos/core#definition,ocr
```

## Property Shapes for Complex Paths

If you don't want the search result IRI to be immediately on the search term triple, you can use an FTS property shape. This allows searching through complex property paths.

### Example Property Shape

```turtle
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix ont: <https://prez.dev/ont/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix ex: <http://example.com/> .
@prefix po: <http://www.essepuntato.it/2008/12/pattern#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .

ex:OCR
    a sh:PropertyShape ;
    a ont:JenaFTSPropertyShape ;
    sh:path ( po:contains po:contains ) ;
    sh:name "Returns document focus nodes for full text search" ;
    dcterms:identifier "ocr" ;
    ont:searchPredicate rdf:value ;
.
```

### Using Property Shapes

Reference the property shape using its `dcterms:identifier` in the `predicates` parameter:

```
/search?q=geology&predicates=ocr
```

This will search for "geology" in `rdf:value` literals, but return search result IRIs that are connected through the `po:contains / po:contains` path.

## Grouping Property Shapes (Union)

Sometimes users want a **named bundle** of multiple FTS property shapes that should be **UNIONed** together, so they can reference the bundle with a single `predicates=` value instead of repeating multiple parameters.

SHACL provides `sh:union`/`sh:or` for *node expressions*, but for Prez FTS we want a declarative container that means “treat these property shapes as UNION branches in the generated search query”.

### Recommended extension (Prez-specific)

Define a **union container** that lists member FTS property shapes. Each member remains a normal `ont:JenaFTSPropertyShape` with its own `sh:path` and `ont:searchPredicate`.

```turtle
@prefix ont: <https://prez.dev/ont/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix ex: <http://example.com/> .

ex:InterestingObjects
    a ont:JenaFTSUnionShape ;
    dcterms:identifier "interesting_objects" ;
    sh:union (
        ex:NameSearch
        ex:TitleSearch
        ex:IdentifierSearch
    ) .

ex:NameSearch
    a ont:JenaFTSPropertyShape ;
    sh:path ex:hasName ;
    ont:searchPredicate <http://www.w3.org/2000/01/rdf-schema#label> ;
    dcterms:identifier "name_search" .

ex:TitleSearch
    a ont:JenaFTSPropertyShape ;
    sh:path ex:hasTitle ;
    ont:searchPredicate <http://purl.org/dc/terms/title> ;
    dcterms:identifier "title_search" .
```

**Intended semantics:** each member property shape becomes its own UNION branch in the generated FTS query.

### When `sh:alternativePath` is enough

If you only need a union of **paths** that share the **same** `ont:searchPredicate`, you can use a standard SHACL `sh:alternativePath` inside a single property shape, e.g.:

```turtle
ex:AltPathSearch
    a ont:JenaFTSPropertyShape ;
    sh:path [ sh:alternativePath ( ex:firstName ex:givenName ) ] ;
    ont:searchPredicate <http://www.w3.org/2000/01/rdf-schema#label> ;
    dcterms:identifier "alt_name" .
```

This is a true property-path union and does not require multiple UNION branches.

## Predicates Parameter Values

The `predicates` parameter accepts:

1. **RDF predicate IRIs** - Direct references to Lucene indexed properties (e.g., `http://www.w3.org/2000/01/rdf-schema#label`, `http://www.w3.org/2004/02/skos/core#definition`)
2. **Property shape identifiers** - The `dcterms:identifier` value of FTS property shapes (e.g., `ocr`)
3. **PropList IRIs** - References to Fuseki text index property lists, as IRIs (e.g., `http://example.com/label` in the example below)

## Fuseki Configuration Example

```turtle
@prefix sdo: <https://schema.org/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<#indexLucene> a text:TextIndexLucene ;
    text:directory "/fuseki/databases/ds/lucene" ;
    text:entityMap <#entMap> ;
    text:propLists
        (
            [
                text:propListProp ex:label ;
                text:props ( rdfs:label sdo:name skos:prefLabel dcterms:title ) ;
            ]
        ) .

<#entMap> a text:EntityMap ;
    text:map (
         [ text:field "label" ; text:predicate rdfs:label ]
         [ text:field "name" ; text:predicate sdo:name ]
         [ text:field "preflabel" ; text:predicate skos:prefLabel ]
         [ text:field "title" ; text:predicate dcterms:title ]
         # ... other mappings
    ) .
```

With this configuration, you can use `http://example.com/label` or `http://www.w3.org/1999/02/22-rdf-syntax-ns#value` in the predicates parameter to search across multiple related properties.
