Prez supports faceted search on listing endpoints, this includes:

`/cql`
`/search`
all endpoints declared a prez:ListingEndpoint. With default settings this includes `/catalogs` `/catalogs/{catalogId}/collections` etc.

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
