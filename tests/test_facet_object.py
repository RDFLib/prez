from rdflib import Graph, URIRef, Namespace
from unittest.mock import patch

from rdflib import Graph, URIRef, Namespace
from sparql_grammar_pydantic import (
    Var,
)

from prez.services.query_generation.facet import FacetQuery
from prez.services.query_generation.shacl import NodeShape

EX = Namespace("http://example.org/")
SHEXT = Namespace("http://example.com/shacl-extension#")


@patch("prez.services.query_generation.shacl.settings")
def test_site_object_property_shape(mock_settings):
    """Provides a PropertyShape instance based on the site-object-facet profile."""
    mock_settings.use_path_aliases = True

    site_profile = """@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix ex: <http://example.org/> .
@prefix prof: <http://www.w3.org/ns/dx/prof/> .
@prefix prez: <https://prez.dev/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix shext: <http://example.com/shacl-extension#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://prez.dev/profile/site-object-facet>
    a prof:Profile , prez:ObjectProfile , prez:ListingProfile ;
    dcterms:identifier "site-obj"^^xsd:token ;
    dcterms:title "Facet sites on properties " ;
    dcterms:description "Allows faceting sites" ;
    sh:property [
        sh:path [
            sh:union (
                     [ sh:path ( ex:hasReport rdf:type ) ; shext:pathAlias ex:ReportFacet ]
                     [ sh:path ( ex:hasWellLog rdf:type ) ; shext:pathAlias ex:WellLogFacet ]
                     [ sh:path ( ex:hasGeomchemistryReport rdf:type ) ; shext:pathAlias ex:GeoChemFacet ]
                     )
                ]
                ] ."""

    g = Graph().parse(data=site_profile)
    ns = NodeShape(
        uri=URIRef("https://prez.dev/profile/site-object-facet"),
        graph=g,
        kind="profile",
        focus_node=Var(value="focus_node"),
    )
    ps = ns.propertyShapes[0]
    fq = FacetQuery(
        original_subselect=None,
        property_shape=ps,
        focus_node_uri="http://example.org/Site1",
    )
    assert (
        str(fq)
        == """CONSTRUCT {
[<https://prez.dev/facetName> ?facetName;<https://prez.dev/facetValue> ?facetValue;<https://prez.dev/facetCount> ?facetCount] 
}
WHERE {
SELECT ?facetName ?facetValue (COUNT(<http://example.org/Site1>) AS ?facetCount)
WHERE {


{
?prof_1_node_1 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?prof_1_node_2 .
?focus_node <http://example.org/hasReport> ?prof_1_node_1 .
BIND(<http://example.org/ReportFacet> AS ?facetName)
BIND(?prof_1_node_2 AS ?facetValue)
}
UNION
{
?prof_1_node_3 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?prof_1_node_4 .
?focus_node <http://example.org/hasWellLog> ?prof_1_node_3 .
BIND(<http://example.org/WellLogFacet> AS ?facetName)
BIND(?prof_1_node_4 AS ?facetValue)
}
UNION
{
?prof_1_node_5 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?prof_1_node_6 .
?focus_node <http://example.org/hasGeomchemistryReport> ?prof_1_node_5 .
BIND(<http://example.org/GeoChemFacet> AS ?facetName)
BIND(?prof_1_node_6 AS ?facetValue)
}
}GROUP BY ?facetName ?facetValue

}"""
    )
