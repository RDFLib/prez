from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic

from prez.app import app
from prez.dependencies import get_repo
from prez.sparql.methods import Repo, PyoxigraphRepo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../tests/data/*/input/*.ttl"):
        store.load(file.read_bytes(), "text/turtle")

    return store


@pytest.fixture(scope="session")
def test_repo(test_store: Store) -> Repo:
    # Create a PyoxigraphQuerySender using the test_store
    return PyoxigraphRepo(test_store)


@pytest.fixture(scope="session")
def test_client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def links(test_client: TestClient):
    r = test_client.get("/v/collection")
    g = Graph().parse(data=r.text)
    vocab_uri = URIRef("http://resource.geosciml.org/classifier/cgi/contacttype")
    vocab_link = g.value(vocab_uri, URIRef(f"https://prez.dev/link", None))
    # vocab_uri = g.value(None, RDF.type, SKOS.ConceptScheme)
    # vocab_link = g.value(member_uri, URIRef(f"https://prez.dev/link", None))
    return vocab_link


def get_curie(test_client: TestClient, iri: str) -> str:
    response = test_client.get(f"/identifier/curie/{iri}")
    if response.status_code != 200:
        raise ValueError(f"Failed to retrieve curie for {iri}. {response.text}")
    return response.text


def test_vocab_listing(test_client: TestClient):
    response = test_client.get(f"/v/vocab?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=response.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/vocprez/expected_responses/vocab_listing_anot.ttl"
    )
    assert isomorphic(expected_graph, response_graph), print(
        f"Missing triples\n{(expected_graph - response_graph).serialize()}",
        f"Extra triples\n{(response_graph - expected_graph).serialize()}",
    )


@pytest.mark.xfail(
    reason="oxigraph's DESCRIBE does not include blank nodes so the expected response is not what will "
    "be returned - route should not need describe query"
)
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

    response = test_client.get(f"/v/vocab/{curie}?_mediatype=text/anot+turtle")
    response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / f"../tests/data/vocprez/expected_responses/{expected_result_file}"
    )
    assert isomorphic(expected_graph, response_graph), f"Failed test: {description}"


# bedding surface works if stepped through - this will be another case of the local SPARQL store not being able to
# process the queries in parallel
@pytest.mark.xfail(reason="query error + issue with oxigraph")
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
    response = test_client.get(
        f"/v/vocab/{curie}/top-concepts?_mediatype=text/anot+turtle"
    )
    response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / f"../tests/data/vocprez/expected_responses/{expected_result_file}"
    )
    assert isomorphic(expected_graph, response_graph), f"Failed test: {description}"


@pytest.mark.xfail(
    reason="issue with oxigraph counting children that do not exist (giving childrenCount 1; should be 0)"
)
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
    response = test_client.get(
        f"/v/vocab/{concept_scheme_curie}/{concept_curie}/narrowers?_mediatype=text/anot+turtle"
    )
    response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / f"../tests/data/vocprez/expected_responses/{expected_result_file}"
    )
    assert isomorphic(expected_graph, response_graph), f"Failed test: {description}"


@pytest.mark.parametrize(
    "concept_scheme_iri, concept_iri, expected_result_file, description",
    [
        # [
        #     "http://linked.data.gov.au/def/borehole-purpose",
        #     "http://linked.data.gov.au/def/borehole-purpose/coal",
        #     "concept-coal.ttl",
        #     "Return the coal concept and its properties.",
        # ],
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
    response = test_client.get(
        f"/v/vocab/{concept_scheme_curie}/{concept_curie}?_mediatype=text/anot+turtle"
    )
    response_graph = Graph(bind_namespaces="rdflib").parse(data=response.text)
    expected_graph = Graph().parse(
        Path(__file__).parent
        / f"../tests/data/vocprez/expected_responses/{expected_result_file}"
    )
    assert isomorphic(expected_graph, response_graph)


def test_collection_listing(test_client: TestClient):
    response = test_client.get(f"/v/collection?_mediatype=text/anot+turtle")
    response_graph = Graph().parse(data=response.text, format="turtle")
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/vocprez/expected_responses/collection_listing_anot.ttl"
    )
    assert isomorphic(expected_graph, response_graph)


# TODO figure out why this fails and yet when run via debugger, passes..
def test_collection_listing_item(test_client: TestClient, links):
    response = test_client.get("/v/collection/cgi:contacttype")
    assert response.status_code == 200
    response_graph = Graph().parse(data=response.text, format="turtle")
    expected_graph = Graph().parse(
        Path(__file__).parent
        / "../tests/data/vocprez/expected_responses/collection_listing_item.ttl"
    )
    assert isomorphic(response_graph, expected_graph), print(
        f"RESPONSE GRAPH\n{response_graph.serialize()},"
        f"EXPECTED GRAPH\n{expected_graph.serialize()}",
        f"MISSING TRIPLES\n{(expected_graph - response_graph).serialize()}",
        f"EXTRA TRIPLES\n{(response_graph - expected_graph).serialize()}",
    )
