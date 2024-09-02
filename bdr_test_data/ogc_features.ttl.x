@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix geo: <http://www.opengis.net/ont/geosparql#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <http://example.org/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix sdo: <http://schema.org/> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix void: <http://rdfs.org/ns/void#> .

ex:DemoCatalog a dcat:Catalog ;
    dcterms:title "Demo Catalog" ;
    dcterms:description "A demonstration catalog containing a dataset with geographic features." ;
    dcterms:hasPart ex:GeoDataset ;
    ex:catalogVersion "1.0" ;
    dcterms:issued "2024-09-02"^^xsd:date .

ex:GeoDataset a dcat:Dataset ;
    dcterms:title "Geographic Dataset" ;
    dcterms:description "A dataset containing a feature collection of geographic features." ;
    ex:datasetTheme "Geography" ;
    dcterms:creator "Jane Doe" .

ex:FeatureCollection a geo:FeatureCollection ;
    dcterms:description "A collection of geographic features representing points of interest." ;
    geo:hasGeometry [
        geo:asWKT "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))"^^geo:wktLiteral
    ] ;
    rdfs:member ex:Feature1, ex:Feature2 ;
    ex:featureCount 2 ;
    void:inDataset ex:GeoDataset .

ex:Feature1 a geo:Feature ;
    rdfs:label "Point of Interest 1" ;
    skos:prefLabel "POI 1" ;
    dcterms:description "A notable location within the feature collection." ;
    geo:hasGeometry [
        geo:asWKT "POINT(5 5)"^^geo:wktLiteral
    ] ;
    ex:category "Landmark" ;
    ex:visitorCount 1000 ;
    sdo:additionalProperty [
        a sdo:PropertyValue ;
        sdo:propertyID "height" ;
        sdo:value "100"^^xsd:integer
    ] ;
    sosa:isFeatureOfInterestOf ex:Observation1 .

ex:Feature2 a geo:Feature ;
    rdfs:label "Point of Interest 2" ;
    dcterms:description "Another notable location within the feature collection." ;
    geo:hasGeometry [
        geo:asWKT "POINT(7 3)"^^geo:wktLiteral
    ] ;
    sdo:spatial [
        geo:hasGeometry [
            geo:asWKT "POLYGON((6 2, 6 4, 8 4, 8 2, 6 2))"^^geo:wktLiteral
        ]
    ] ;
    ex:category "Historical Site" ;
    ex:yearEstablished 1850 ;
    sdo:additionalProperty [
        a sdo:PropertyValue ;
        sdo:propertyID "age" ;
        sdo:value "174"^^xsd:integer
    ] .

ex:Observation1 a sosa:Observation ;
    sosa:hasFeatureOfInterest ex:Feature1 ;
    sosa:observedProperty ex:Temperature ;
    sosa:hasResult [
        a sdo:PropertyValue ;
        sdo:value "25.5"^^xsd:decimal ;
        sdo:unitCode "CEL"
    ] ;
    sosa:resultTime "2024-09-02T12:00:00Z"^^xsd:dateTime .