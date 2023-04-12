# Developer README

This documentation is to assist developers of Prez, not users or installers.

## Content delivered by Prez

Prez returns:
- RDF data for specified objects
- RDF data for lists of objects
- Annotated RDF* for specified objects
- Annotated RDF* for lists of objects
- Available Profiles
- An alternates profile for every object or listing, listing all available profiles and mediatypes
- OpenAPI documentation for the API

\* Annotated RDF is RDF which includes labels, descriptions, and explanatory properties for all RDF terms. The predicates Prez looks for are rdfs:label, `dcterms:description`, and `dcterms:provenance`. The list of predicates Prez looks for can be extended in the profiles.

## Internal links
The objects Prez delivers RDF for have URIs that uniquely identify them. Prez delivers RDF for these objects at URLs on the web. These URLs and URIs are not required to be the same, and frequently are not. For objects that Prez holds information for, it is helpful if Prez tells users the URL of these when they are referenced elsewhere in the API. This is in two places:
1. Listings of objects, for example `dcat:Datasets` at the `/s/datasets` endpoint; and
2. Links to related objects, where the API holds information on the related object.\
In these cases, in the annotated RDF mediatype (`text/anot+turtle`) URL paths are provided which link to the related object

For cases where URIs and URLs for a given object differ slightly, URL redirection can be used to send users to the Prez URL instance which displays information for the object.

## High Level Sequence

Prez follows the following logic to determine what information to return, based on a profile, and in what mediatype to return it.

1. Determine the URI for an object or listing of objects:
- For objects:
   - Directly supplied through the /{x}/object?uri=<abc> query string argument where x is the Prez subsystem (v, s, or c)
   - From the object's identifier with a datatype of `prez:slug`. These identifiers are used in the URL path; Prez reads them from the path when it receives a request at that URL.

- For listings:
  - Determine the URI of the parent class which contains the listed objects.
    - For the most top level objects (see _Top Level Class_ in the [Glossary](#Glossary)) in each Prez instance a Prez specific object contains the top level objects. For example, the a prez:DatasetList has rdfs:member the dcat:Dataset objects. This data is generated on startup if not supplied, as detailed in [Appendix C](#appendix-c---sparql-insert-queries-for-support-graphs).
    - For non top level objects, the URI is determined using a SPARQL query

2. Get all classes for the object or object listing
   _Steps 1 and 2 are implemented in the `prez/models/*` modules using Pydantic classes_
3. Determine the profile and mediatype to use for the object. This is implemented as a SPARQL query and takes into account:
   1. The classes of the object
   2. Available profiles and mediatypes
   3. Requested profiles and mediatypes
   4. Default profiles and mediatypes
The logic used to determine the profile and mediatype is detailed in section x.

4. Build a SPARQL query:
   - For objects
      1. A SPARQL CONSTRUCT query is used, roughly equivalent to a DESCRIBE query, but with configurable blank node depth, and relations to other objects. The following properties can be specified in profiles to configure which information is returned for an object:

		| Description                                                                    | Property                                    |
		|---------------------------------------------------------------------------------|---------------------------------------------|
		| The depth of blank nodes to return. | `prez:blankNodeDepth`                       |
		| predicates to include                                                          | `sh:path`                                   |
		| predicates to exclude                                                          | `sh:path` in conjunction with `dash:hidden` |
		| inverse path predicates to include                                             | `sh:inversePath`                            |
		| sequence path predicates to include, expressed as an RDF list.                 | `sh:sequencePath`                           |

      2. Where _Relation Properties_ (see the [Glossary](#Glossary) for definition) are specified in the profile, a second SPARQL CONSTRUCT query is used, as detailed in object listings:
   - For object listings:
     1. A SPARQL CONSTRUCT query is used, with a LIMIT and OFFSET, and `prez:link` internal API URL paths are generated for each member object returned.
5. Execute the SPARQL query
6. If the mediatype requested is NOT annotated RDF (`text/anot+turtle`), return the results of 5, else retrieve the annotations:
   1. Check Prez cache for annotations
   2. For terms without annotations in the cache, query the triplestore for annotations
   3. Cache any annotations returned from the triplestore
   4. Return the annotations merged with the results of the SPARQL query in step 5.

## Profile and mediatype selection logic
The following logic is used to determine the profile and mediatype to be returned:

1. If a profile and mediatype are requested, they are returned if a matching profile which has the requested mediatype is found, otherwise the default profile for the most specific class is returned, with its default mediatype.
2. If a profile only is requested, if it can be found it is returned, otherwise the default profile for the most specific class is returned. In both cases the default mediatype is returned.
3. If a mediatype only is requested, the default profile for the most specific class is returned, and if the requested mediatype is available for that profile, it is returned, otherwise the default mediatype for that profile is returned.
4. If neither a profile nor mediatype is requested, the default profile for the most specific class is returned, with the default mediatype for that profile.

The SPARQL query used to select the profile is given in [Appendix D](appendix-d---example-profile-and-mediatype-selection-sparql-query).

## Startup Routine
1. Check the SPARQL endpoints can be reached. A blank query (`ASK {}`) is used to test this. The SPARQL endpoints are not health checked post startup.
2. Find search methods, add these to an in memory dictionary with pydantic models, and add a reference to the available search methods in the system graph (available at the root endpoint)
3. Create an in memory profile graph, containing all profiles in the `prez/profiles` directory, and any additional profiles available in the triplestore (declared as a `http://www.w3.org/ns/dx/prof/Profile`)
4. Count the number of objects in each _Collection Class_
5. Check for the required support graphs, and if the required support graphs are not present, create them. The SPARQL INSERT query used to create the support graphs is detailed in [Appendix C](#appendix-c---sparql-insert-queries-for-support-graphs). The required support graphs are:
   1. A system support graph (e.g. `https://prez.dev/vocprez-system-graph` for VocPrez). See example in [Appendix F](appendix-f---example-system-support-graph).
   2. A support graph per _Collection Class_ (see the [Glossary](#Glossary) for definition). See example in [Appendix G](appendix-g---example-system-support-graph-for-a-feature-collection).


## Search
Search methods can be defined as RDF. See the examples in `prez/reference_data/search_methods`.
At present the parameterised SPARQL queries accept the following parameters: PREZ and TERM (for a search term).
These parameters are substituted into the SPARQL query using the `string.Template` module. This module substitutes where $PREZ and $TERM are found in the query.
You must also escape any $ characters in the query using a second $.

## Scaled instances of Prez
When using Prez for large volumes of data, it is recommended the support graph data is created offline. This includes:
- Identifiers for all objects (a `dcterms:identifier`)
- Collection counts
This information must be placed in graphs following Prez naming conventions in order for Prez to find them.

## Prez and Altr-ext namespaces
TODO separate ontology
The following terms are in the Prez namespace:

| Term                                                                | Description                                                                                                          |
|---------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `prez:slug`                                                         | A slug is a unique identifier for an object. In Prez they must be unique **among all members of a _Collection Class_** |
| `prez:count`                                                        | The number of objects in an instance of a _Collection Class_                                                         |
| `prez:DatasetList`, `prez:FeatureCollectionList`, `prez:FeatureList` | Classes used to describe lists of `dcat:Dataset`, `geo:FeatureCollection`, and `geo:Feature` instances respectively  |
| `prez:CatalogList`                                                  | Class used to describe a list of `dcat:Catalog` instances                                                            |
| `prez:SchemesList`, `prez:VocPrezCollectionList`                    | Class used to describe a list of `skos:ConceptScheme` and `skos:Collection` instances respectively                  |
TODO altr-ext - this may be merged with altr


## Glossary
| Term | Description                                                                                    |
|-----------------------|------------------------------------------------------------------------------------------------|
| Collection Class | `skos:Collection`, `skos:ConceptScheme`, `dcat:Dataset`, `geo:FeatureCollection`, `dcat:Catalog` |
| Top Level Class | `skos:Collection`, `skos:ConceptScheme`, `dcat:Dataset`, `dcat:Catalog` |

## Appendix A - Example SPARQL query for an object
```sparql
CONSTRUCT {
  <https://linked.data.gov.au/datasets/gnaf> ?p ?o1.
  ?o1 ?p2 ?o2.
  ?o2 ?p3 ?o3.
}
WHERE {
  {
    <https://linked.data.gov.au/datasets/gnaf> ?p ?o1.
    OPTIONAL {
      FILTER(ISBLANK(?o1))
      ?o1 ?p2 ?o2.
      OPTIONAL {
        FILTER(ISBLANK(?o2))
        ?o2 ?p3 ?o3.
      }
    }
  }
  MINUS {
    <https://linked.data.gov.au/datasets/gnaf> dct:identifier ?o1.
    FILTER((DATATYPE(?o1)) = prez:slug)
  }
}
```
## Appendix B - Example SPARQL query for an object listing
```sparql
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

CONSTRUCT {
  <https://prez.dev/DatasetList> ?outbound_children ?item .
  ?item prez:link ?outbound_children_link .
}
WHERE {
  <https://prez.dev/DatasetList> ?outbound_children ?item .
  ?item dcterms:identifier ?outbound_children_id .
  FILTER(DATATYPE(?outbound_children_id) = prez:slug)
  VALUES ?outbound_children { <http://www.w3.org/2000/01/rdf-schema#member> }

  BIND(CONCAT("/s/datasets", "/", STR(?outbound_children_id))AS ?outbound_children_link)

}
LIMIT 20
OFFSET 0
```
## Appendix C - SPARQL INSERT queries for support graphs
### C.1 - SpacePrez Insert Support Graphs
```sparql
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
INSERT {
  GRAPH prez:spaceprez-system-graph {
    ?support_graph_uri prez:hasContextFor ?instance_of_main_class .
    ?collectionList rdfs:member ?instance_of_top_class .
    ?instance_of_main_class dcterms:identifier ?prez_id .
  }
  GRAPH ?support_graph_uri { ?member dcterms:identifier ?prez_mem_id . }
}
WHERE {
  {
    ?instance_of_main_class a ?collection_class .
    VALUES ?collection_class { <http://www.w3.org/ns/dcat#Dataset>
      <http://www.opengis.net/ont/geosparql#FeatureCollection> }
    OPTIONAL {?instance_of_top_class a ?topmost_class
      VALUES ?topmost_class { <http://www.w3.org/ns/dcat#Dataset> }
    }
    MINUS { GRAPH prez:spaceprez-system-graph {?a_context_graph prez:hasContextFor ?instance_of_main_class}
    }
    OPTIONAL {?instance_of_main_class dcterms:identifier ?id
      BIND(DATATYPE(?id) AS ?dtype_id)
      FILTER(?dtype_id = xsd:token)
    }
    OPTIONAL { ?instance_of_main_class rdfs:member ?member
      OPTIONAL {?member dcterms:identifier ?mem_id
        BIND(DATATYPE(?mem_id) AS ?dtype_mem_id)
        FILTER(?dtype_mem_id = xsd:token) } }
  }
  BIND(
    IF(?topmost_class=dcat:Dataset, prez:DatasetList,
      IF(?topmost_class=dcat:Catalog,prez:CatalogList,
        IF(?topmost_class=skos:ConceptScheme,prez:SchemesList,
          IF(?topmost_class=skos:Collection,prez:VocPrezCollectionList,"")))) AS ?collectionList)
  BIND(STRDT(COALESCE(STR(?id),MD5(STR(?instance_of_main_class))), prez:slug) AS ?prez_id)
  BIND(STRDT(COALESCE(STR(?mem_id),MD5(STR(?member))), prez:slug) AS ?prez_mem_id)
  BIND(URI(CONCAT(STR(?instance_of_main_class),"/support-graph")) AS ?support_graph_uri)
}
```
### C.2 - CatPrez Insert Support Graphs
```sparql
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
INSERT {
  GRAPH prez:catprez-system-graph {
    ?support_graph_uri prez:hasContextFor ?instance_of_main_class .
    ?collectionList rdfs:member ?instance_of_top_class .
    ?instance_of_main_class dcterms:identifier ?prez_id .
  }
  GRAPH ?support_graph_uri { ?member dcterms:identifier ?prez_mem_id . }
}
WHERE {
  {
    ?instance_of_main_class a ?collection_class .
    VALUES ?collection_class { <http://www.w3.org/ns/dcat#Catalog>
      <http://www.w3.org/ns/dcat#Resource> }
    OPTIONAL {?instance_of_top_class a ?topmost_class
      VALUES ?topmost_class { <http://www.w3.org/ns/dcat#Catalog> }
    }
    MINUS { GRAPH prez:catprez-system-graph {?a_context_graph prez:hasContextFor ?instance_of_main_class}
    }
    OPTIONAL {?instance_of_main_class dcterms:identifier ?id
      BIND(DATATYPE(?id) AS ?dtype_id)
      FILTER(?dtype_id = xsd:token)
    }
    OPTIONAL { ?instance_of_main_class dcterms:hasPart ?member
      OPTIONAL {?member dcterms:identifier ?mem_id
        BIND(DATATYPE(?mem_id) AS ?dtype_mem_id)
        FILTER(?dtype_mem_id = xsd:token) } }
  }
  BIND(
    IF(?topmost_class=dcat:Dataset, prez:DatasetList,
      IF(?topmost_class=dcat:Catalog,prez:CatalogList,
        IF(?topmost_class=skos:ConceptScheme,prez:SchemesList,
          IF(?topmost_class=skos:Collection,prez:VocPrezCollectionList,"")))) AS ?collectionList)
  BIND(STRDT(COALESCE(STR(?id),MD5(STR(?instance_of_main_class))), prez:slug) AS ?prez_id)
  BIND(STRDT(COALESCE(STR(?mem_id),MD5(STR(?member))), prez:slug) AS ?prez_mem_id)
  BIND(URI(CONCAT(STR(?instance_of_main_class),"/support-graph")) AS ?support_graph_uri)
}
```
### C.3 - VocPrez Insert Support Graphs
```sparql
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
INSERT {
  GRAPH prez:vocprez-system-graph {
    ?support_graph_uri prez:hasContextFor ?instance_of_main_class .
    ?collectionList rdfs:member ?instance_of_top_class .
    ?instance_of_main_class dcterms:identifier ?prez_id .
  }
  GRAPH ?support_graph_uri { ?member dcterms:identifier ?prez_mem_id . }
}
WHERE {
  {
    ?instance_of_main_class a ?collection_class .
    VALUES ?collection_class { <http://www.w3.org/2004/02/skos/core#ConceptScheme>
      <http://www.w3.org/2004/02/skos/core#Collection> }
    OPTIONAL {?instance_of_top_class a ?topmost_class
      VALUES ?topmost_class { <http://www.w3.org/2004/02/skos/core#ConceptScheme>
        <http://www.w3.org/2004/02/skos/core#Collection> }
    }
    MINUS { GRAPH prez:vocprez-system-graph {?a_context_graph prez:hasContextFor ?instance_of_main_class}
    }
    OPTIONAL {?instance_of_main_class dcterms:identifier ?id
      BIND(DATATYPE(?id) AS ?dtype_id)
      FILTER(?dtype_id = xsd:token)
    }
    OPTIONAL { {?instance_of_main_class ^skos:inScheme ?member }
      UNION
      { ?instance_of_main_class skos:member ?member }
      OPTIONAL {?member dcterms:identifier ?mem_id
        BIND(DATATYPE(?mem_id) AS ?dtype_mem_id)
        FILTER(?dtype_mem_id = xsd:token) } }
  }
  BIND(
    IF(?topmost_class=dcat:Dataset, prez:DatasetList,
      IF(?topmost_class=dcat:Catalog,prez:CatalogList,
        IF(?topmost_class=skos:ConceptScheme,prez:SchemesList,
          IF(?topmost_class=skos:Collection,prez:VocPrezCollectionList,"")))) AS ?collectionList)
  BIND(STRDT(COALESCE(STR(?id),MD5(STR(?instance_of_main_class))), prez:slug) AS ?prez_id)
  BIND(STRDT(COALESCE(STR(?mem_id),MD5(STR(?member))), prez:slug) AS ?prez_mem_id)
  BIND(URI(CONCAT(STR(?instance_of_main_class),"/support-graph")) AS ?support_graph_uri)
}
```
## Appendix D - Example Profile and Mediatype Selection SPARQL query
This SPARQL query determines the profile and mediatype to return based on user requests,
defaults, and the availability of these in profiles.

NB: Most specific class refers to the rdfs:Class of an object which has the most specific rdfs:subClassOf links to the general class delivered by that API endpoint. The general classes delivered by each API endpoint are:

**SpacePrez**:
/s/datasets -> `prez:DatasetList`
/s/datasets/{ds_id} -> `dcat:Dataset`
/s/datasets/{ds_id}/collections/{fc_id} -> `geo:FeatureCollection`
/s/datasets/{ds_id}/collections -> `prez:FeatureCollectionList`
/s/datasets/{ds_id}/collections/{fc_id}/features -> `geo:Feature`

**VocPrez**:
/v/schemes -> `skos:ConceptScheme`
/v/collections -> `skos:Collection`
/v/schemes/{cs_id}/concepts -> `skos:Concept`

**CatPrez**:
/c/catalogs -> `dcat:Catalog`
/c/catalogs/{cat_id}/datasets -> `dcat:Dataset`

This is an example query for SpacePrez requesting the Datasets listing from a web browser. Note the following components of the query are populated in Python:
1. The `?class` VALUES
2. A `?req_profile` value (not present in this query as no profile was requested)
3. Nested IF statements, based on the mediatypes in the HTTP request.
```sparql
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?profile ?title ?class (count(?mid) as ?distance) ?req_profile ?def_profile ?format ?req_format ?def_format ?token

WHERE {
  VALUES ?class {<https://prez.dev/DatasetList>}
  ?class rdfs:subClassOf* ?mid .
  ?mid rdfs:subClassOf* ?general_class .
  VALUES ?general_class { dcat:Dataset geo:FeatureCollection prez:FeatureCollectionList prez:FeatureList geo:Feature
    skos:ConceptScheme skos:Concept skos:Collection prez:DatasetList prez:VocPrezCollectionList prez:SchemesList
    prez:CatalogList dcat:Catalog dcat:Resource }
  ?profile altr-ext:constrainsClass ?class ;
           altr-ext:hasResourceFormat ?format ;
           dcterms:identifier ?token ;
           dcterms:title ?title .

  BIND(EXISTS { ?shape sh:targetClass ?class ;
                       altr-ext:hasDefaultProfile ?profile } AS ?def_profile)
  BIND(
    IF(?format="image/webp", "1",
      IF(?format="application/xml", "0.9",
        IF(?format="text/html", "1",
          IF(?format="*/*", "0.8",
            IF(?format="image/avif", "1",
              IF(?format="application/xhtml+xml", "1", ""))))))
    AS ?req_format)
  BIND(EXISTS { ?profile altr-ext:hasDefaultResourceFormat ?format } AS ?def_format)
}

GROUP BY ?class ?profile ?req_profile ?def_profile ?format ?req_format ?def_format
ORDER BY DESC(?req_profile) DESC(?distance) DESC(?def_profile) DESC(?req_format) DESC(?def_format)
```
## Appendix E - Example profiles
### Appendix E.1 - Example system profile
The following snippet shows a system profile for Prez which declares the default profile to be used for objects with a class of `dcat:Dataset`.
```turtle
<http://kurrawong.net/profile/prez>
    a prof:Profile ;
    dcterms:identifier "prez" ;
    dcterms:description "A profile for the Prez Linked Data API" ;
    skos:prefLabel "Prez profile" ;
    altr-ext:hasDefaultResourceFormat "text/anot+turtle" ;
    altr-ext:hasNodeShape [
        a sh:NodeShape ;
        sh:targetClass dcat:Dataset ;
        altr-ext:hasDefaultProfile <https://www.w3.org/TR/vocab-dcat/>
    ] .
```
### Appendix E.2 - Example mediatype declarations
The following snippet shows how to define which mediatypes a resource constrained by that profile should be available in, via the `altr-ext:hasResourceFormat` property. It also shows how default mediatypes can be declared, via the `altr-ext:hasDefaultResourceFormat` property.
```turtle
<http://www.opengis.net/def/geosparql>
    a prof:Profile ;
    dcterms:description "An RDF/OWL vocabulary for representing spatial information" ;
    dcterms:identifier "geo" ;
    dcterms:title "GeoSPARQL" ;
    altr-ext:constrainsClass geo:Feature ;
    altr-ext:hasDefaultResourceFormat "text/anot+turtle" ;
    altr-ext:hasResourceFormat
        "application/ld+json" ,
        "application/rdf+xml" ,
        "text/anot+turtle" ,
        "text/turtle" ;
.
```
### Appendix E.3 - Example mediatype declarations
The following snippet shows a profile which constrains a number of classes, and declares two NodeShapes which state the following:
1. For a `geo:FeatureCollection`, only include properties where the predicate is one of those listed under `sh:path`. In this case, `rdfs:member` has been deliberately omitted as instances of `geo:FeatureCollection` can have significant numbers of `rdfs:member` relations which can create query performance issues. A sample of the Feature Collections members can still be included, using the method described in (2.) below
2. Instances of `geo:FeatureCollection`, `prez:FeatureCollectionList`, and `prez:FeatureList`, have a number of member objects (related via the `rdfs:member` relation) which are delivered via Prez. With this information Prez:
   1. Creates internal links when returning annotated RDF, such that HTML views can include internal links
   2. Uses a LIMIT/OFFSET query to ensure that only a sample of the members are returned, to avoid query performance issues
```turtle
<http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30>
    a prof:Profile ;
    dcterms:description "The OGC API Features specifies the behavior of Web APIs that provide access to features in a dataset in a manner independent of the underlying data store." ;
    dcterms:identifier "oai" ;
    dcterms:title "OGC API Features" ;
    altr-ext:constrainsClass
        dcat:Dataset ,
        geo:FeatureCollection ,
        geo:Feature ,
        prez:FeatureCollectionList ,
        prez:FeatureList ;
    altr-ext:hasDefaultResourceFormat "text/anot+turtle" ;
    altr-ext:hasResourceFormat
        "text/anot+turtle" ,
        "application/geo+json" ;
    altr-ext:hasNodeShape [
        a sh:NodeShape ;
        sh:targetClass geo:FeatureCollection ;
        sh:path rdf:type,
                dcterms:identifier,
                dcterms:title,
                geo:hasBoundingBox,
                dcterms:provenance,
                rdfs:label,
                dcterms:description ;
    ] ,
    [  a sh:NodeShape ;
        sh:targetClass geo:FeatureCollection , prez:FeatureCollectionList , prez:FeatureList ;
        altr-ext:outboundChildren rdfs:member ;
    ]
.
```
### Appendix E.4 - Example inbound links
The following VocPrez VocPub profile shows how to use a number of declarations:
1. Inbound Children: for Concept Schemes, include concepts delivered via Prez that are skos:inScheme the Concept Scheme. NB sh:inversePath could also be used but this will not create internal links in the HTML view, nor limit the number of results returned.
2. Outbound Parents: for Concepts, include the objects the Concept is skos:inScheme of. NB an 'open' profile declaring no constraints would return these triples by default - by declaring the predicate in a profile, an internal link will be created in the HTML view (and the number of linked results limited).
```turtle
<https://w3id.org/profile/vocpub>
    a prof:Profile ;
    dcterms:description "This is a profile of the taxonomy data model SKOS - i.e. SKOS with additional constraints." ;
    dcterms:identifier "vocpub" ;
    dcterms:title "VocPub" ;
    altr-ext:hasLabelPredicate skos:prefLabel ;
    altr-ext:constrainsClass
        skos:ConceptScheme ,
        skos:Concept ,
        skos:Collection ,
        prez:SchemesList ,
        prez:VocPrezCollectionList ;
    altr-ext:hasDefaultResourceFormat "text/turtle" ;
    altr-ext:hasResourceFormat
        "application/ld+json" ,
        "application/rdf+xml" ,
        "text/anot+turtle" ,
        "text/turtle" ;
    altr-ext:hasNodeShape [
        a sh:NodeShape ;
        sh:targetClass skos:ConceptScheme ;
        altr-ext:outboundChildren skos:hasTopConcept ;
    ] ;
    altr-ext:hasNodeShape [
        a sh:NodeShape ;
        sh:targetClass skos:Collection ;
        altr-ext:outboundChildren skos:member ;
    ] ;
    altr-ext:hasNodeShape [
        a sh:NodeShape ;
        sh:targetClass skos:ConceptScheme ;
        altr-ext:inboundChildren skos:inScheme ;
    ] ;
    altr-ext:hasNodeShape [
        a sh:NodeShape ;
        sh:targetClass skos:Concept ;
        altr-ext:outboundParents skos:inScheme ;
    ]
.
```
## Appendix F - Example system support graph
```turtle
@prefix addr:    <http://w3id.org/profile/anz-address/> .
@prefix ahgf:    <https://linked.data.gov.au/def/geofabric/> .
@prefix dcat:    <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix geo:     <http://www.opengis.net/ont/geosparql#> .
@prefix geofab:  <https://linked.data.gov.au/def/geofabric#> .
@prefix gnaf:    <https://linked.data.gov.au/datasets/gnaf/> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix prov:    <http://www.w3.org/ns/prov#> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sand:    <http://example.com/datasets/sandgate/> .
@prefix sdo:     <https://schema.org/> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix vcard:   <http://www.w3.org/2006/vcard/ns#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .

<https://prez.dev/DatasetList>
        rdfs:member
                <http://example.com/datasets/sandgate> ,
                <https://linked.data.gov.au/datasets/gnaf> ,
                <https://linked.data.gov.au/datasets/geofabric> .

<http://example.com/datasets/sandgate/roads/support-graph>
        <https://prez.dev/hasContextFor>
                sand:roads .

<https://linked.data.gov.au/datasets/geofabric/fc/catchments/support-graph>
        <https://prez.dev/hasContextFor>
                <https://linked.data.gov.au/datasets/geofabric/fc/catchments> .

sand:catchments  dcterms:identifier  "catchments"^^<https://prez.dev/slug> .

<https://linked.data.gov.au/datasets/gnaf>
        dcterms:identifier  "gnaf"^^<https://prez.dev/slug> .

sand:facilities  dcterms:identifier  "facilities"^^<https://prez.dev/slug> .

sand:roads  dcterms:identifier  "roads"^^<https://prez.dev/slug> .

<http://example.com/datasets/sandgate/facilities/support-graph>
        <https://prez.dev/hasContextFor>
                sand:facilities .

<https://linked.data.gov.au/datasets/geofabric/fc/catchments>
        dcterms:identifier  "catchments"^^<https://prez.dev/slug> .

sand:support-graph  <https://prez.dev/hasContextFor>
                <http://example.com/datasets/sandgate> .

<https://linked.data.gov.au/datasets/geofabric/support-graph>
        <https://prez.dev/hasContextFor>
                <https://linked.data.gov.au/datasets/geofabric> .

gnaf:address  dcterms:identifier  "address"^^<https://prez.dev/slug> .

<https://linked.data.gov.au/datasets/gnaf/address/support-graph>
        <https://prez.dev/hasContextFor>
                gnaf:address .

gnaf:support-graph  <https://prez.dev/hasContextFor>
                <https://linked.data.gov.au/datasets/gnaf> .

<https://linked.data.gov.au/datasets/geofabric>
        dcterms:identifier  "geofabric"^^<https://prez.dev/slug> .

<http://example.com/datasets/sandgate/floods/support-graph>
        <https://prez.dev/hasContextFor>
                sand:floods .

<http://example.com/datasets/sandgate/catchments/support-graph>
        <https://prez.dev/hasContextFor>
                sand:catchments .

<http://example.com/datasets/sandgate>
        dcterms:identifier  "sandgate"^^<https://prez.dev/slug> .

sand:floods  dcterms:identifier  "floods"^^<https://prez.dev/slug> .
```
### Appendix G - Example system support graph for a Feature Collection
```turtle
@prefix dcterms: <http://purl.org/dc/terms/> .

<https://example.com/catchment/cabbage-tree-creek>
        dcterms:identifier  "cabbage-tree"^^<https://prez.dev/slug> .

<https://linked.data.gov.au/datasets/geofabric/hydroid/102208961>
        dcterms:identifier  "102208961"^^<https://prez.dev/slug> .

<https://example.com/catchment/cabbage-tree-creek-geojson>
        dcterms:identifier  "cabbage-tree-geojson"^^<https://prez.dev/slug> .

<https://example.com/catchment/kedron-brook>
        dcterms:identifier  "kedron"^^<https://prez.dev/slug> .

<https://linked.data.gov.au/datasets/geofabric/hydroid/102208962>
        dcterms:identifier  "102208962"^^<https://prez.dev/slug> .
```
