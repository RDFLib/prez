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
    include_predicates = []
    exclude_predicates = []
    bnode_depth = 2
    returned = generate_construct(
        object_uri, include_predicates, exclude_predicates, bnode_depth
    )
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
