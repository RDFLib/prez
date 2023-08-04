import os
import subprocess
from pathlib import Path
from time import sleep

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph
from rdflib.compare import isomorphic

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")


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


def get_curie(test_client: TestClient, iri: str) -> str:
    with test_client as client:
        response = client.get(f"/identifier/curie/{iri}")
        if response.status_code != 200:
            raise ValueError(f"Failed to retrieve curie for {iri}. {response.text}")
        return response.text


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
            "http://linked.data.gov.au/def2/borehole-purpose",
            "concept_scheme_with_children.ttl",
            "Return concept scheme and a prez:childrenCount of 8",
        ],
        [
            "http://linked.data.gov.au/def2/borehole-purpose-no-children",
            "concept_scheme_no_children.ttl",
            "Return concept scheme and a prez:childrenCount of 0",
        ],
    ],
)
def test_concept_scheme(
    test_client: TestClient, iri: str, expected_result_file: str, description: str
):
    curie = get_curie(test_client, iri)

    with test_client as client:
        response = client.get(f"/v/vocab/{curie}?_mediatype=text/anot+turtle")
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
            "http://linked.data.gov.au/def2/borehole-purpose",
            "concept_scheme_top_concepts_with_children.ttl",
            "Return concept scheme and a prez:childrenCount of 8",
        ],
        [
            "http://linked.data.gov.au/def2/borehole-purpose-no-children",
            "empty.ttl",
            "Return concept scheme and a prez:childrenCount of 0",
        ],
        [
            "http://data.bgs.ac.uk/ref/BeddingSurfaceStructure",
            "beddingsurfacestructure_top_concepts.ttl",
            "Top concepts have the correct annotation values for reg:status and color",
        ],
    ],
)
def test_concept_scheme_top_concepts(
    test_client: TestClient, iri: str, expected_result_file: str, description: str
):
    curie = get_curie(test_client, iri)

    with test_client as client:
        response = client.get(
            f"/v/vocab/{curie}/top-concepts?_mediatype=text/anot+turtle"
        )
        response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / f"../data/vocprez/expected_responses/{expected_result_file}"
        )
        assert isomorphic(expected_graph, response_graph), f"Failed test: {description}"


@pytest.mark.parametrize(
    "concept_scheme_iri, concept_iri, expected_result_file, description",
    [
        [
            "http://linked.data.gov.au/def2/borehole-purpose",
            "http://linked.data.gov.au/def/borehole-purpose/coal",
            "concept-with-2-narrower-concepts.ttl",
            "Return concept with 2 narrower concepts.",
        ],
        [
            "http://linked.data.gov.au/def2/borehole-purpose",
            "http://linked.data.gov.au/def2/borehole-purpose/open-cut-coal-mining",
            "empty.ttl",
            "Return nothing, no children.",
        ],
    ],
)
def test_concept_narrowers(
    test_client: TestClient,
    concept_scheme_iri: str,
    concept_iri: str,
    expected_result_file: str,
    description: str,
):
    concept_scheme_curie = get_curie(test_client, concept_scheme_iri)
    concept_curie = get_curie(test_client, concept_iri)

    with test_client as client:
        response = client.get(
            f"/v/vocab/{concept_scheme_curie}/{concept_curie}/narrowers?_mediatype=text/anot+turtle"
        )
        response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / f"../data/vocprez/expected_responses/{expected_result_file}"
        )
        assert isomorphic(expected_graph, response_graph), f"Failed test: {description}"


@pytest.mark.parametrize(
    "concept_scheme_iri, concept_iri, expected_result_file, description",
    [
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            "http://linked.data.gov.au/def/borehole-purpose/coal",
            "concept-coal.ttl",
            "Return the coal concept and its properties.",
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            "http://linked.data.gov.au/def/borehole-purpose/open-cut-coal-mining",
            "concept-open-cut-coal-mining.ttl",
            "Return the open-cut-coal-mining concept and its properties.",
        ],
    ],
)
def test_concept(
    test_client: TestClient,
    concept_scheme_iri: str,
    concept_iri: str,
    expected_result_file: str,
    description: str,
):
    concept_scheme_curie = get_curie(test_client, concept_scheme_iri)
    concept_curie = get_curie(test_client, concept_iri)

    with test_client as client:
        response = client.get(
            f"/v/vocab/{concept_scheme_curie}/{concept_curie}?_mediatype=text/anot+turtle"
        )
        response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
        expected_graph = Graph().parse(
            Path(__file__).parent
            / f"../data/vocprez/expected_responses/{expected_result_file}"
        )
        assert isomorphic(expected_graph, response_graph)


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
