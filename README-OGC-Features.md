Prez provides an OGC Features compliant API

The API is mounted as a sub application at `"/catalogs/{catalogId}/collections/{recordsCollectionId}/features"` by default.
It can be mounted at a different path by setting the configuration setting `ogc_features_mount_path` (or corresponding upper cased environment variable).

Queryables are a part of the OGC Features specifications which provide a listing of which parameters can be queried.
The queryables are a flat set of properties on features.

Because Prez consumes an RDF Knowledge Graph, it is desirable to query more than top level properties.
To achieve this, Prez provides a mechanism to declare paths through the graph as queryables.
To declare these paths, you can use SHACL.

An example is provided below:
```
@prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix dwc: <http://rs.tdwg.org/dwc/terms/> .
@prefix ex: <http://example.com/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix sname: <https://fake-scientific-name-id.com/name/afd/> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:BDRScientificNameQueryableShape
  a sh:PropertyShape ;
  a cql:Queryable ;
  sh:path (
      [ sh:inversePath sosa:hasFeatureOfInterest ]
      sosa:hasMember
      sosa:hasResult
      dwc:scientificNameID
      ) ;
  sh:name "Scientific Name" ;
  dcterms:identifier "scientificname" ;
  sh:datatype xsd:string ;
  sh:in (
      sname:001
      sname:002
) ;
.
```
It is recommended that templated SPARQL queries are used to periodically update the `sh:in` values, which correspond to enumerations.
# TODO other SHACL predicates can be reused to specify min/max values, etc. where the range is numeric and enumerations are not appropriate.

When Prez starts, it will query the remote repository (typically a triplestore) for all Queryables.
It queries for them using a CONSTRUCT query, serializes this as JSON-LD, and does a minimal transformation to produce the OGC Features compliant response. 
The query is:
```
"""
    PREFIX cql: <http://www.opengis.net/doc/IS/cql2/1.0/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    CONSTRUCT {
    ?queryable cql:id ?id ;
    	cql:name ?title ;
    	cql:datatype ?type ;
    	cql:enum ?enums .
    }
    WHERE {?queryable a cql:Queryable ;
        dcterms:identifier ?id ;
        sh:name ?title ;
        sh:datatype ?type ;
        sh:in/rdf:rest*/rdf:first ?enums ;
    }
    """
```
And the output after transformation is of the form (which is the format required for OGC Features):
```
{
  "$schema": "https://json-schema.org/draft/2019-09/schema",
  "$id": "http://localhost:8000/catalogs/dtst:bdr/collections/syn:68a782a8-d7fe-4b3e-8377-c76c9cc245cc/features/queryables",
  "type": "object",
  "title": "Global Queryables",
  "description": "Global queryable properties for all collections in the OGC Features API.",
  "properties": {
    "scientificname": {
      "title": "Scientific Name",
      "type": "string",
      "enum": [
        "https://fake-scientific-name-id.com/name/afd/001",
        "https://fake-scientific-name-id.com/name/afd/002",
      ]
    }
  }
}
```

Separately, Prez internally translates the declared SHACL Property Path expression into SPARQL and injects this into queries when the queryable, e.g. `scientificname`, in the example above, is requested.