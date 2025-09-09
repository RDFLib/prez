# Fuseki FTS (Full-Text Search) Integration

Prez integrates with Apache Jena Fuseki's full-text search capabilities to enable efficient text search across RDF data.

## Basic Usage

Use the `predicates` URL query parameter to specify which indexed properties or property shapes to search:

```
/search?q=geological&predicates=rdfs:label,skos:definition,ocr
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

ex:GSWA-OCR
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

## Predicates Parameter Values

The `predicates` parameter accepts:

1. **RDF predicate URIs** - Direct references to Lucene indexed properties (e.g., `rdfs:label`, `skos:definition`)
2. **Property shape identifiers** - The `dcterms:identifier` value of FTS property shapes (e.g., `ocr`)
3. **PropList URIs** - References to Fuseki text index property lists (e.g., `ex:label` in the example below)

## Fuseki Configuration Example

```turtle
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
         [ text:field "fulltext" ; text:predicate rdf:value ]
         # ... other mappings
    ) .
```

With this configuration, you can use `ex:label` or `rdf:value` in the predicates parameter to search across multiple related properties.