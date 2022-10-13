import pytest
from prez.services.sparql_new import *
from rdflib import URIRef

from tests.local_sparql_store.store import load_spaceprez_graph


def test_generate_bnode_construct():
    depth = 4
    returned = generate_bnode_construct(depth)
    expected = """	?o1 ?p2 ?o2 .
	?o2 ?p3 ?o3 .
	?o3 ?p4 ?o4 .
	?o4 ?p5 ?o5 ."""
    assert returned == expected


def test_generate_bnode_select():
    depth = 4
    returned = generate_bnode_select(depth)
    expected = """	OPTIONAL {
		FILTER(ISBLANK(?o1))
		?o1 ?p2 ?o2 .
		OPTIONAL {
			FILTER(ISBLANK(?o2))
			?o2 ?p3 ?o3 .
			OPTIONAL {
				FILTER(ISBLANK(?o3))
				?o3 ?p4 ?o4 .
				OPTIONAL {
					FILTER(ISBLANK(?o4))
					?o4 ?p5 ?o5 .
				}
			}
		}
	}"""
    assert returned == expected


def test_generate_construct_open():
    object_uri = "http://example.com"
    profile = {"bnode_depth": 2}
    returned = generate_item_construct(object_uri, profile)
    expected = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CONSTRUCT {
    <http://example.com> ?p ?o1 .
	?o1 ?p2 ?o2 .
	?o2 ?p3 ?o3 .
  }
WHERE {
    <http://example.com> !rdfs:member ?o1 ;
        ?p ?o1 .

 	OPTIONAL {
		FILTER(ISBLANK(?o1))
		?o1 ?p2 ?o2 .
		OPTIONAL {
			FILTER(ISBLANK(?o2))
			?o2 ?p3 ?o3 .
		}
	}
}
"""
    assert returned == expected


def test_generate_include_predicates():
    include_predicates = [
        URIRef("https://example.com"),
        URIRef("https://example2.com"),
        URIRef("https://example3.com"),
    ]
    returned = generate_include_predicates(include_predicates)
    expected = """VALUES ?p{
<https://example.com>
<https://example2.com>
<https://example3.com>
}"""
    assert returned == expected


@pytest.mark.asyncio
async def test_get_labels():
    spaceprez_graph = load_spaceprez_graph()
    labels = await get_labels(spaceprez_graph)


def test_get_labels_from_tbox_cache():
    terms = {
        URIRef("http://www.opengis.net/ont/geosparql#asWKT"),
        URIRef("http://www.opengis.net/ont/geosparql#hasGeometry"),
        URIRef("https://linked.data.gov.au/def/geofabric/ContractedCatchment"),
        URIRef("http://purl.org/dc/terms/title"),
        URIRef("http://www.opengis.net/ont/geosparql#hasMetricArea"),
        URIRef("http://www.opengis.net/ont/geosparql#Feature"),
        URIRef("https://linked.data.gov.au/def/geofabric/NonContractedArea"),
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
        URIRef("http://purl.org/dc/terms/type"),
    }
    uncached_terms, labels_from_cache = get_labels_from_tbox_cache(terms)
    assert len(uncached_terms) == 7
    assert len(labels_from_cache) == 2


def test_generate_listing_construct_datasets():
    returned = generate_listing_construct((DCAT.Dataset, None), page=1, per_page=20)
    expected = """PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

CONSTRUCT { ?item dcterms:identifier ?id }
WHERE {
    ?item a <http://www.w3.org/ns/dcat#Dataset> ;
          dcterms:identifier ?id .
  	FILTER(DATATYPE(?id) = xsd:token)
    } LIMIT 20 OFFSET 0
    """
    assert returned == expected


def test_generate_listing_construct_feature_collections():
    returned = generate_listing_construct(
        (GEO.FeatureCollection, URIRef("http://parent-dataset")), page=1, per_page=20
    )
    expected = """PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

CONSTRUCT { ?item dcterms:identifier ?id }
WHERE {
	<http://parent-dataset> rdfs:member ?item .
    ?item a <http://www.opengis.net/ont/geosparql#FeatureCollection> ;
          dcterms:identifier ?id .
  	FILTER(DATATYPE(?id) = xsd:token)
    } LIMIT 20 OFFSET 0
    """
    assert returned == expected


def test_generate_listing_construct_features():
    returned = generate_listing_construct(
        (GEO.Feature, URIRef("http://parent-feature-collection")), page=1, per_page=20
    )
    expected = """PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

CONSTRUCT { ?item dcterms:identifier ?id }
WHERE {
	<http://parent-feature-collection> rdfs:member ?item .
    ?item a <http://www.opengis.net/ont/geosparql#Feature> ;
          dcterms:identifier ?id .
  	FILTER(DATATYPE(?id) = xsd:token)
    } LIMIT 20 OFFSET 0
    """
    assert returned == expected


def test_generate_listing_construct_pagination():
    returned = generate_listing_construct(
        (GEO.Feature, URIRef("http://parent-feature-collection")), page=30, per_page=40
    )
    expected = """PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

CONSTRUCT { ?item dcterms:identifier ?id }
WHERE {
	<http://parent-feature-collection> rdfs:member ?item .
    ?item a <http://www.opengis.net/ont/geosparql#Feature> ;
          dcterms:identifier ?id .
  	FILTER(DATATYPE(?id) = xsd:token)
    } LIMIT 40 OFFSET 1160
    """
    assert returned == expected
