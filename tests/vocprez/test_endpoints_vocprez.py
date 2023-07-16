import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")


# @pytest.fixture(scope="module")
# def a_concept_link(vp_test_client, a_vocab_link):
#     # get the first concept endpoint
#     r = vp_test_client.get(a_vocab_link)
#     g = Graph().parse(data=r.text)
#     concept_uri = next(g.subjects(predicate=SKOS.inScheme, object=None))
#     concept_link = g.value(concept_uri, URIRef(f"https://prez.dev/link", None))
#     return concept_link
#
#
# def test_concept_scheme_with_no_children(vp_test_client, a_vocab_link):
#     with vp_test_client as client:
#         r = client.get(
#             f"{a_vocab_link}?_mediatype=text/anot+turtle"
#         )  # hardcoded to a smaller vocabulary - sparql store has poor performance w/ CONSTRUCT
#         response_graph = Graph(bind_namespaces="rdflib").parse(data=r.text)
#         expected_graph = Graph().parse(
#             Path(__file__).parent
#             / "../data/vocprez/expected_responses/borehole-purpose-no-children.ttl"
#         )
#         assert isomorphic(expected_graph, response_graph)
#
#

#
#
# def test_concept(vp_test_client, a_concept_link):
#     with vp_test_client as client:
#         r = client.get(f"{a_concept_link}?_mediatype=text/anot+turtle")
#         response_graph = Graph().parse(data=r.text)
#         expected_graph = Graph().parse(
#             Path(__file__).parent
#             / "../data/vocprez/expected_responses/concept_anot.ttl"
#         )
#         assert response_graph.isomorphic(expected_graph), print(
#             f"Graph delta:{(expected_graph - response_graph).serialize()}"
#         )
#
#


@pytest.fixture(scope="module")
def test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3031"])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app

    return TestClient(app)


def get_prez_link(test_client: TestClient, iri: str) -> str:
    with test_client as client:
        response = client.get("/v/vocab")
        if response.status_code != 200:
            raise ValueError("Failed to retrieve vocab list")
        graph = Graph().parse(data=response.text)
        concept_link = graph.value(URIRef(iri), URIRef(f"https://prez.dev/link", None))
        return str(concept_link)


def test_vocab_listing(test_client: TestClient):
    with test_client as client:
        response = client.get(f"/v/vocab?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=response.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/vocprez/expected_responses/vocab_listing_anot.ttl"
        )
        assert isomorphic(expected_graph, response_graph)


@pytest.mark.parametrize(
    "iri, expected_result_file, description",
    [
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            "concept_scheme_with_children.ttl",
            "Return concept scheme and a prez:childrenCount of 8",
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose-no-children",
            "concept_scheme_no_children.ttl",
            "Return concept scheme and a prez:childrenCount of 0",
        ],
    ],
)
def test_concept_scheme(
    test_client: TestClient, iri: str, expected_result_file: str, description: str
):
    prez_link = get_prez_link(test_client, iri)

    with test_client as client:
        response = client.get(f"{prez_link}?_mediatype=text/anot+turtle")
        response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / f"../data/vocprez/expected_responses/{expected_result_file}"
        )
        assert isomorphic(expected_graph, response_graph), f"Failed test: {description}"


@pytest.mark.parametrize(
    "iri, expected_result_file, description",
    [
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            "concept_scheme_top_concepts_with_children.ttl",
            "Return concept scheme and a prez:childrenCount of 8",
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose-no-children",
            "empty.ttl",
            "Return concept scheme and a prez:childrenCount of 0",
        ],
    ],
)
def test_concept_scheme_top_concepts(
    test_client: TestClient, iri: str, expected_result_file: str, description: str
):
    prez_link = get_prez_link(test_client, iri)

    with test_client as client:
        response = client.get(f"{prez_link}/top-concepts?_mediatype=text/anot+turtle")
        response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / f"../data/vocprez/expected_responses/{expected_result_file}"
        )
        assert isomorphic(expected_graph, response_graph), f"Failed test: {description}"


def test_collection_listing(test_client: TestClient):
    with test_client as client:
        response = client.get(f"/v/collection?_mediatype=text/anot+turtle")
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/vocprez/expected_responses/collection_listing_anot.ttl"
        )
        assert isomorphic(expected_graph, response_graph)


def test_collection_listing_item(test_client: TestClient):
    with test_client as client:
        response = client.get("/v/collection/cgi:contacttype")
        assert response.status_code == 200
        response_graph = Graph().parse(data=response.text, format="turtle")
        expected_graph = Graph().parse(
            Path(__file__).parent
            / "../data/vocprez/expected_responses/collection_listing_item.ttl"
        )
        assert isomorphic(response_graph, expected_graph)
