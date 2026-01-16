from unittest.mock import patch

from rdflib import Graph, URIRef, Namespace
from sparql_grammar_pydantic import (
    IRI,
    Var,
)

from prez.services.query_generation.facet import FacetQuery
from prez.services.query_generation.shacl import NodeShape

EX = Namespace("http://example.org/")
SHEXT = Namespace("http://example.com/shacl-extension#")


@patch("prez.services.query_generation.shacl.settings")
def test_site_object_property_shape(mock_settings):
    """
    Test that object facets use the focus node IRI in WHERE patterns.

    This simulates the actual usage where NodeShape is created with Var but
    the change to facet.py:261 uses IRI when focus_node_uri is provided.
    """
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
    focus_node_uri = "http://example.org/Site1"

    # IMPORTANT: This simulates what create_facets_query does:
    # Before the fix: always used Var("focus_node")
    # After the fix: uses IRI(focus_node_uri) when focus_node_uri is provided
    # So to test the fix, we need to test with the NEW behavior:
    focus_node = IRI(value=focus_node_uri) if focus_node_uri else Var(value="focus_node")
    ns = NodeShape(
        uri=URIRef("https://prez.dev/profile/site-object-facet"),
        graph=g,
        kind="profile",
        focus_node=focus_node,
    )
    ps = ns.propertyShapes[0]
    fq = FacetQuery(
        original_subselect=None,
        property_shape=ps,
        focus_node_uri=focus_node_uri,
    )
    query_str = str(fq)

    # With the change, the focus node IRI should be used in WHERE patterns
    assert "<http://example.org/Site1> <http://example.org/hasReport>" in query_str
    assert "<http://example.org/Site1> <http://example.org/hasWellLog>" in query_str
    assert "<http://example.org/Site1> <http://example.org/hasGeomchemistryReport>" in query_str

    # The focus node IRI should be in the COUNT expression
    assert "COUNT(<http://example.org/Site1>)" in query_str

    # Should NOT use ?focus_node variable when focus_node_uri is provided
    assert "?focus_node <http://example.org/hasReport>" not in query_str
    assert "?focus_node <http://example.org/hasWellLog>" not in query_str
    assert "?focus_node <http://example.org/hasGeomchemistryReport>" not in query_str


@patch("prez.services.query_generation.shacl.settings")
def test_focus_node_var_vs_iri_comparison(mock_settings):
    """
    Test demonstrating the bug and the fix for focus_node in object facet queries.

    BUG: When facet.py:261 uses Var("focus_node"), the query incorrectly uses ?focus_node
    FIX: When facet.py:261 uses the focus_node variable (IRI when focus_node_uri provided),
         the query correctly uses the specific IRI in WHERE patterns.

    This test creates two scenarios:
    1. NodeShape with Var (OLD BROKEN CODE) - shows ?focus_node in query
    2. NodeShape with IRI (NEW FIXED CODE) - shows actual IRI in query
    """
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
                     )
                ]
                ] ."""

    g = Graph().parse(data=site_profile)
    focus_node_uri = "http://example.org/Site1"

    # Scenario 1: OLD BROKEN CODE - NodeShape created with Var (facet.py:261 before fix)
    ns_with_var = NodeShape(
        uri=URIRef("https://prez.dev/profile/site-object-facet"),
        graph=g,
        kind="profile",
        focus_node=Var(value="focus_node"),  # This is what line 261 currently does (WRONG)
    )
    fq_broken = FacetQuery(
        original_subselect=None,
        property_shape=ns_with_var.propertyShapes[0],
        focus_node_uri=focus_node_uri,
    )
    broken_query = str(fq_broken)

    # Scenario 2: NEW FIXED CODE - NodeShape created with IRI (facet.py:261 after fix)
    ns_with_iri = NodeShape(
        uri=URIRef("https://prez.dev/profile/site-object-facet"),
        graph=g,
        kind="profile",
        focus_node=IRI(value=focus_node_uri),  # This is what line 261 SHOULD do (CORRECT)
    )
    fq_fixed = FacetQuery(
        original_subselect=None,
        property_shape=ns_with_iri.propertyShapes[0],
        focus_node_uri=focus_node_uri,
    )
    fixed_query = str(fq_fixed)

    # Demonstrate the bug: broken version uses ?focus_node
    assert "?focus_node <http://example.org/hasReport>" in broken_query, \
        "Broken code uses ?focus_node variable (this demonstrates the bug)"

    # Validate the fix: fixed version uses the actual IRI
    assert f"<{focus_node_uri}> <http://example.org/hasReport>" in fixed_query, \
        "Fixed code uses the actual IRI in WHERE patterns"
    assert "?focus_node <http://example.org/hasReport>" not in fixed_query, \
        "Fixed code should not use ?focus_node variable"

    # Both should have the IRI in the COUNT (this always worked)
    assert f"COUNT(<{focus_node_uri}>)" in broken_query
    assert f"COUNT(<{focus_node_uri}>)" in fixed_query
