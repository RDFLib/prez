# Developer Readme

## Content delivered by Prez

Prez returns:
- RDF data for specified objects
- RDF data for lists of objects
- Annotated* RDF for specified objects
- Annotated* RDF for lists of objects
- Available Profiles
- An alternates profile for every object or listing, listing all available profiles and mediatypes
- OpenAPI documentation for the API

\* Annotated RDF is RDF which includes labels, descriptions, and explanatory properties for all RDF terms. The predicates Prez looks for are rdfs:label, dcterms:description, and dcterms:provenance. The list of predicates Prez looks for can be extended in the profiles.

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
    - For the most top level objects (see _Top Level Class_ in the [Glossary](#Glossary)) in each Prez instance a Prez specific object contains the top level objects. For example, the a prez:DatasetList has rdfs:member the dcat:Dataset objects. This data is generated on startup if not supplied, as detailed in section x.
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

		| Description                                                                     | Property                                    |
		|---------------------------------------------------------------------------------|---------------------------------------------|
		| The depth of blank nodes to return. Blank nodes are returned as nested objects. | `prez:blankNodeDepth`                       |
		| predicates to include                                                           | `sh:path`                                   |
		| predicates to exclude                                                           | `sh:path` in conjunction with `dash:hidden` |
		| inverse path predicates to include                                              | `sh:inversePath`                            |
		| sequence path predicates to include, expressed as an RDF list.                  | `sh:sequencePath`                           |

      2. Where 'relation' properties are specified in the profile (i.e. inboundChildren, outboundChildren, inboundParents, outboundParents), a second SPARQL CONSTRUCT query is used, as detailed in object listings:
   - For object listings:
     1. A SPARQL CONSTRUCT query is used, with a LIMIT and OFFSET, and `prez:link` internal API URL paths are generated for each member object returned.
5. Execute the SPARQL query
6. If the mediatype requested is NOT annotated RDF (`text/anot+turtle`), return the results of 5, else retrieve the annotations:
   1. Check Prez cache for annotations
   2. For terms without annotations in the cache, query the triplestore for annotations
   3. Cache any annotations returned from the triplestore
   4. Return the annotations merged with the results of the SPARQL query in step 5.

## Startup Routine
1. Check the SPARQL endpoints can be reached. A blank query (`ASK {}`) is used to test this. The SPARQL endpoints are not health checked post startup.
2. Create an in memory profile graph, containing all profiles in the `prez/profiles` directory, and any additional profiles available in the triplestore (declared as a `http://www.w3.org/ns/dx/prof/Profile`)
3. Count the number of objects in each _Collection Class_
4. Check for the required support graphs, and if the required support graphs are not present, create them. The SPARQL INSERT query used to create the support graphs is detailed in [Appendix A](#Appendix A). The required support graphs are:
   1. A system support graph (e.g. `https://prez.dev/vocprez-system-graph` for VocPrez)
   2. A support graph per _Collection Class_ (see the [Glossary](#Glossary) for definition)


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
| `prez:SchemesList`, `prez:VocPrezCollectionList`                    | Class used to describe a list of `skos:ConceptScheme` and `skos:Collection` instances resprectively                  |
TODO altr-ext - this may be merged with altr


## Glossary
| Term | Description                                                                                    |
|-----------------------|------------------------------------------------------------------------------------------------|
| Collection Class | `skos:Collection`, `skos:ConceptScheme`, `dcat:Dataset`, `geo:FeatureCollection`, `dcat:Catalog` |
| Top Level Class | `skos:Collection`, `skos:ConceptScheme`, `dcat:Dataset`, `dcat:Catalog` |

## Appendix A - SPARQL INSERT queries for support graphs
### A.1 - SpacePrez
```
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
### A.2 - CatPrez
```
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
### A.3 - VocPrez
```
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
## Appendix B
