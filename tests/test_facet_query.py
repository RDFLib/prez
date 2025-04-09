import pytest
from rdflib import URIRef, Graph, SH, Namespace # Added Graph, SH, Namespace
from unittest.mock import patch # Added patch
from sparql_grammar_pydantic import (
    GroupGraphPattern,
    GroupGraphPatternSub,
    IRI,
    SelectClause,
    SubSelect,
    TriplesBlock,  # Import TriplesBlock
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)

from prez.services.query_generation.facet import FacetQuery
from prez.services.query_generation.shacl import PropertyShape # Added PropertyShape

# Define SHEXT namespace locally for tests - corrected namespace
SHEXT = Namespace("http://example.com/shacl-extension#")

@pytest.fixture(scope="module")
@patch("prez.services.query_generation.shacl.settings") # Mock settings for the fixture
def gswa_property_shape_fixture(mock_settings):
    """Provides a PropertyShape instance based on the gswa_like_profile."""
    mock_settings.use_path_aliases = True # Set the required setting for the test case
    gswa_profile = """PREFIX altr-ext: <http://www.w3.org/ns/dx/connegp/altr-ext#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX geo: <http://www.opengis.net/ont/geosparql#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX prez: <https://prez.dev/>
    PREFIX prof: <http://www.w3.org/ns/dx/prof/>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX shext: <http://example.com/shacl-extension#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX schema: <https://schema.org/>
    PREFIX sosa: <http://www.w3.org/ns/sosa/>
    PREFIX ex: <https://example.com/dataset/gswa/>

    <https://prez.dev/profile/formation-top>
        a prof:Profile , prez:ListingProfile ;
        dcterms:identifier "formation-top"^^xsd:token ;
        dcterms:description "Formation top data extract to match WAPIMS interface table" ;
        dcterms:title "Formation top table" ;
        altr-ext:constrainsClass sosa:Sample , <https://linked.data.gov.au/def/borehole/Bore> ;
        altr-ext:hasDefaultResourceFormat "text/anot+turtle" ;
        altr-ext:hasResourceFormat "application/geo+json" ,
            "application/ld+json" ,
            "application/anot+ld+json" ,
            "application/rdf+xml" ,
            "text/anot+turtle" ,
            "text/turtle" ;
        altr-ext:hasNodeShape [
            a sh:NodeShape ;
            sh:targetClass rdfs:Resource , <https://linked.data.gov.au/def/borehole/Bore> ;
            altr-ext:hasDefaultProfile <https://prez.dev/profile/formation-top>
        ] ;
    sh:property [
        sh:path [
                sh:union (
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] ) ;
                            shext:pathAlias <https://example.com/sample-parent> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] schema:identifier ) ;
                            shext:pathAlias <https://example.com/sample-parent-identifier> ;
                        ]
                        sosa:isSampleOf
                        [
                            sh:path ( sosa:isSampleOf schema:identifier ) ;
                            shext:pathAlias <https://example.com/sample-identifier> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] geo:sfWithin ) ;
                            shext:pathAlias <https://example.com/sample-parent-location> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] ex:originatesFrom ) ;
                            shext:pathAlias <https://example.com/sample-parent-origin> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf schema:depth ex:topDepth ) ;
                            shext:pathAlias <https://my_prop_path> ;
                            sh:facet true
                        ]
                        [
                            sh:path ( sosa:isSampleOf schema:depth ex:bottomDepth ) ;
                            shext:pathAlias <https://example.com/sample-bottom-depth> ;
                        ]
                        schema:name
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:observedProperty ) ;
                            shext:pathAlias <https://example.com/feature-observed-property> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:minValue ex:hasAgeName ) ;
                            shext:pathAlias <https://example.com/feature-result-min-age-name> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:minValue ex:hasAgeName schema:value) ;
                            shext:pathAlias <https://example.com/feature-result-min-age-value> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:maxValue ex:hasAgeName ) ;
                            shext:pathAlias <https://example.com/feature-result-max-age-name> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:maxValue ex:hasAgeName schema:value) ;
                            shext:pathAlias <https://example.com/feature-result-max-age-value> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:comment ) ;
                            shext:pathAlias <https://example.com/feature-result-comment> ;
                        ]
                        schema:citation
                        schema:comment
                )
            ]
        ] ;
    ."""
    g = Graph().parse(data=gswa_profile)
    path_bn = g.value(subject=URIRef("https://prez.dev/profile/formation-top"), predicate=SH.property)
    focus_node_var = Var(value="focus_node")
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )
    return ps



def test_facet_query_skeleton_instantiation(gswa_property_shape_fixture): # Added fixture argument
    """
    Tests that the basic FacetQuery skeleton can be instantiated
    with a minimal original SubSelect.
    """
    # Minimal original WHERE clause: ?focus_node a ?type .
    original_where = WhereClause(
        group_graph_pattern=GroupGraphPattern(
            content=GroupGraphPatternSub(
                # Use from_tssp_list class method
                triples_block=TriplesBlock.from_tssp_list(
                    [
                        TriplesSameSubjectPath.from_spo(
                            Var(value="focus_node"),
                            IRI(value="http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                            Var(value="type"),
                        )
                    ]
                )
            )
        )
    )


    # Minimal original SubSelect
    original_subselect = SubSelect(
        select_clause=SelectClause(variables_or_all=[Var(value="focus_node")]),
        where_clause=original_where,
    )

    # Instantiate FacetQuery with empty facet properties for now
    facet_query = FacetQuery(
        original_subselect=original_subselect, facet_properties=[], property_shape=gswa_property_shape_fixture
    )

    # Assert that the object was created
    assert facet_query is not None
    assert isinstance(facet_query, FacetQuery)

    # Basic check on the generated query string
    query_string = facet_query.to_string()
    assert "CONSTRUCT" in query_string
    assert "http://example.org/text#facetName" in query_string
    assert "http://example.org/text#facetValue" in query_string
    assert "http://example.org/text#facetCount" in query_string
    assert "WHERE" in query_string
    assert "SELECT" in query_string
    assert "COUNT(DISTINCT ?focus_node)" in query_string
    assert "GROUP BY ?facetName ?facetValue" in query_string
    # Check if the original triple pattern is roughly there
    assert "?focus_node <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?type" in query_string
