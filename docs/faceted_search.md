Prez supports faceted search on all listing and object endpoints:

**Listing endpoints:**
`/cql`
`/search`
all endpoints declared a prez:ListingEndpoint. With default settings this includes `/catalogs` `/catalogs/{catalogId}/collections` etc.

**Object endpoints:**
Faceted search can also be performed on all object endpoints (prez:ObjectEndpoint) by providing the focus node IRI directly. In this case, no subselect is performed and faceting works the same way for the properties of the single object.

> Note: At this point faceting is only supported for categorical properties (though faceting will correctly produce / execute queries on properties with continuous values the output is probably not desirable).

Faceting profiles use a subset of predicates as regular prez profiles, as such, regular prez profiles _can_ be reused for faceting. It is recommended **not** to do this, but instead define separate faceting profiles which only define the properties to be faceted on, and make the profiles easier to read by not including the properties not needed for faceting.

The following must be included in the faceting profile:

- A property path on a `sh:NodeShape` which includes a `sh:union` clause with one or more properties to facet on.
  - The properties must be either:
    - SHACL predicate paths (i.e. direct properties, not sequence, inverse paths etc.); or 
  - Complex property paths (sequence, inverse etc.) can utilise `shext:pathAlias`. Note to use path aliases in general you must set the `USE_PATH_ALIASES` environment variable to `true`;
  - The properties must currently be nested under a `sh:union` clause.
- The profile must be declared both a `prof:Profile` and `prez:ListingProfile`
- It must declare a `dcterms:title`, `dcterms:identifier` and `dcterms:description`.

Faceted search is an opt in feature that is only run when the `facet_profile` query string argument is supplied. The facet profile URI, curie, or DCTERMS identifier of the profile (with or without datatype `xsd:token`) can be supplied to identify the facet profile to use.

A minimal facet profile demonstrating both a direct property to facet on and one with a path alias is shown below:

```turtle
<https://prez.dev/profile/facet-by-type>
    a prof:Profile , prez:ListingProfile ;
    dcterms:identifier "facet-type"^^xsd:token ;
    dcterms:title "Facet things by type and material" ;
    dcterms:description "Allows faceting by rdf:type and sdo:material" ;
    sh:property [ 
        sh:path [ 
            sh:union (
                         rdf:type 
                         <https://schema.org/material>
                     )
                ]
                ] .
```

The generated facet queries are of the form:
```sparql
CONSTRUCT {
  [
      <https://prez.dev/facetName> ?facetName;
      <https://prez.dev/facetValue> ?facetValue;
      <https://prez.dev/facetCount> ?facetCount
  ] 
}
WHERE {
  SELECT ?facetName ?facetValue (COUNT(?focus_node) AS ?facetCount)
  WHERE {
    {
        # for listing, CQL, and search, a subselect is included
      SELECT DISTINCT ?focus_node
      WHERE {
        ?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://linked.data.gov.au/def/borehole/Borehole> .
        ?focus_node <http://www.w3.org/ns/dcat#resource>|^<http://www.w3.org/ns/sosa/isSampleOf> ?path_node_1 .
        ?path_node_1 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?path_node_classes_1
        VALUES ?path_node_classes_1{ <https://schema.org/Report> <http://www.w3.org/ns/sosa/Sample> <https://www.gswa.com/WellLog> <https://www.gswa.com/Observation> <https://schema.org/ImageObject> <https://www.gswa.com/LoggingRun>  }
      }
    }
    {
      ?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?prof_1_node_1
      BIND(<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> AS ?facetName)
      BIND(?prof_1_node_1 AS ?facetValue)
    }
    UNION
    {
      ?focus_node <https://schema.org/material> ?prof_1_node_2
      BIND(<https://schema.org/material> AS ?facetName)
      BIND(?prof_1_node_2 AS ?facetValue)
    }
  }GROUP BY ?facetName ?facetValue
}
```

## Open Faceting

Open faceting is allowed, meaning you can perform faceted search without providing a search term by using only the `facet_profile` parameter:

```
/search?facet_profile=xyz
```

When no search term is provided, Prez automatically injects a `?focus_node a ?type` triple in the subselect query. This ensures that only instances of classes are faceted on, rather than attempting to facet across all nodes in the dataset.

**Performance Considerations:**

Open faceting works well for smaller datasets, but performance can become an issue with larger datasets since it needs to process all class instances without any filtering constraints.

For larger datasets, it is recommended to:
- Perform a search first to narrow the result set
- Add additional filters or search terms to reduce the scope (using parameters: filter, bbox, datetime, q)
- Use a separate full text search/faceting implementation designed for large-scale operations such as open search or lucene
```

## Lucene-native faceting

Where the data is served through a Jena Fuseki Lucene index, a facet profile can
name the index's own fields instead of describing SHACL property paths. Lucene
then counts the facets itself, which is faster and avoids restating in SHACL what
the index configuration already knows.

The predicates live in the `https://prez.dev/jena-lucene/` namespace:

```turtle
@prefix luc:   <https://prez.dev/jena-lucene/> .
@prefix field: <urn:jena:lucene:field#> .
```

`luc:flatFacets` takes one or more field IRIs, for categorical facets:

```turtle
<https://prez.dev/profile/facet-by-commodity>
    a prof:Profile , prez:ListingProfile , prez:ObjectProfile ;
    dcterms:identifier "facet-commodity"^^xsd:token ;
    dcterms:title "Facet on commodity" ;
    dcterms:description "Counts results by the indexed commodity field" ;
    luc:flatFacets field:targetCommodity , field:sourceSystem .
```

`luc:rangeFacets` takes a node carrying `luc:field` and, optionally,
`luc:bucketBoundaries`, for numeric and date facets. The boundaries are a JSON
array, where `null` at either end means unbounded:

```turtle
<https://prez.dev/profile/facet-by-date>
    a prof:Profile , prez:ListingProfile , prez:ObjectProfile ;
    dcterms:identifier "facet-date"^^xsd:token ;
    dcterms:title "Facet on year created" ;
    dcterms:description "Counts results into year ranges" ;
    luc:rangeFacets [
        luc:field field:dateCreated ;
        luc:bucketBoundaries "[null, 2020, 2022, 2024, null]"
    ] .
```

Both predicates can appear on the same profile.

Two things to know about how this behaves:

- **The field must be facetable in the index.** A field IRI only works if its
  entry in the Fuseki assembler configuration carries `idx:facetable true`.
  Naming a field that is not facetable yields no counts for it.
- **Prez chooses the mechanism from the profile.** A profile carrying
  `luc:flatFacets` or `luc:rangeFacets` uses Lucene-native faceting; any other
  profile falls back to the `sh:property` union path described above. So the
  SHACL form keeps working for non-Lucene deployments, and a profile is migrated
  by replacing its `sh:property` block with the field IRIs, dropping the
  `shext:pathAlias` triples with it.

A `luc:rangeFacets` node with no `luc:field` is skipped with a warning, as is a
`luc:bucketBoundaries` value that is not parseable JSON.
