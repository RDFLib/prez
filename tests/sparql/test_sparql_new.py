import subprocess
import sys
from pathlib import Path
from time import sleep

import pytest
from rdflib import DCAT, SKOS
from rdflib.namespace import GEO

from models.vocprez_item import VocabItem
from prez.services.sparql_new import *

PREZ_DIR = Path(__file__).parent.parent.parent.absolute() / "prez"
LOCAL_SPARQL_STORE = Path(Path(__file__).parent.parent / "local_sparql_store/store.py")
sys.path.insert(0, str(PREZ_DIR.parent.absolute()))
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def sparql_test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3033"])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app

    return TestClient(app)


@pytest.fixture(scope="module")
def sparql_vocab_id(sparql_test_client):
    r = sparql_test_client.get("/vocab")
    g = Graph().parse(data=r.text)
    vocab_uri = g.value(
        URIRef("https://kurrawong.net/prez/memberList"), RDFS.member, None
    )
    vocab_id = g.value(vocab_uri, DCTERMS.identifier, None)
    return vocab_id


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
    item = SpatialItem(uri=URIRef("http://example.com"))
    profile = {"bnode_depth": 2}
    returned = generate_item_construct(item, profile)
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
    labels_queries = await get_annotation_properties(spaceprez_graph)


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
    uncached_terms, labels_from_cache = get_annotations_from_tbox_cache(terms)
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


def test_get_profile_predicates_sequence(sp_test_client):
    profile_uri = URIRef("https://w3id.org/profile/vocpub")
    profile = {"uri": profile_uri}
    general_class = SKOS.ConceptScheme
    preds = get_profile_predicates(profile, general_class)
    assert preds[3] == [
        [
            URIRef("http://www.w3.org/2000/01/rdf-schema#member"),
            URIRef("http://purl.org/dc/terms/identifier"),
        ]
    ]


def test_construct_query_with_sequence(sparql_test_client, sparql_vocab_id):
    profile_uri = URIRef("https://w3id.org/profile/vocpub")
    profile = {"uri": profile_uri}
    item = VocabItem(uri=profile_uri, url="/vocab")
    returned = generate_item_construct(item, profile)
    expected = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CONSTRUCT {
	<https://w3id.org/profile/vocpub> ?p ?o1 .
	<https://w3id.org/profile/vocpub> <http://www.w3.org/2000/01/rdf-schema#member> ?seq_o1 .
	?seq_o1 <http://purl.org/dc/terms/identifier> ?seq_o2 .
	?o1 ?p2 ?o2 .
	?o2 ?p3 ?o3 .
}
WHERE {
	<https://w3id.org/profile/vocpub> ?p ?o1 .
	<https://w3id.org/profile/vocpub> <http://www.w3.org/2000/01/rdf-schema#member> ?seq_o1 .
	?seq_o1 <http://purl.org/dc/terms/identifier> ?seq_o2 .
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
