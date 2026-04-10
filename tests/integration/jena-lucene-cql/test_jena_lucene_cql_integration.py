from contextlib import contextmanager
import gzip
from pathlib import Path
from time import sleep
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.compare import graph_diff, to_isomorphic
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage

from prez.app import assemble_app
from prez.config import Settings, settings as global_settings


EX = Namespace("http://example.org/mining/")
FIXTURE_DIR = Path(__file__).parent
DATA_DIR = FIXTURE_DIR / "data"
CONFIG_PATH = FIXTURE_DIR / "config.ttl"
DOCKERFILE_DIR = FIXTURE_DIR
IMAGE_TAG = f"prez-jena-lucene-cql:{uuid4().hex}"
EXPECTED_GOLD_TURTLE = """\
@prefix altr-ext: <http://www.w3.org/ns/dx/connegp/altr-ext#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix shext: <http://example.com/shacl-extension#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix prof: <http://www.w3.org/ns/dx/prof/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex1: <http://example.org/mining/> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prfl: <https://w3id.org/profile/> .
@prefix profile: <https://prez.dev/profile/> .
@prefix exm: <https://example.com/> .
@prefix ex: <http://example.org/> .
@prefix prez: <https://prez.dev/> .
ex1:bh-bod-001 a ex1:Borehole .
prez:SearchResult prez:count 2 .
<urn:hash:046be7b484e960f3c47939b8aa3959a11bb0b88329e76758b51b9fc293a1fcee> prez:searchResultWeight "2.7743397"^^xsd:float ;
    prez:searchResultURI ex1:bh-bod-001 ;
    prez:hasSearchMatch <urn:match:046be7b484e960f3c47939b8aa3959a11bb0b88329e76758b51b9fc293a1fcee> ;
    a prez:SearchResult .
<urn:match:046be7b484e960f3c47939b8aa3959a11bb0b88329e76758b51b9fc293a1fcee>
    prez:searchResultPredicate <urn:jena:lucene:field#title> ;
    prez:searchResultMatch "BOD-DDH-001 Boddington Deep Diamond Hole" ;
    a prez:SearchResultMatch .
ex1:bh-cad-001 a ex1:Borehole .
<urn:hash:9425a9e2e5c80570d7b3642bed78f5c48c244e4c63e417abf9a8811a9ba90381> prez:searchResultWeight "2.7743397"^^xsd:float ;
    prez:searchResultURI ex1:bh-cad-001 ;
    prez:hasSearchMatch <urn:match:9425a9e2e5c80570d7b3642bed78f5c48c244e4c63e417abf9a8811a9ba90381> ;
    a prez:SearchResult .
<urn:match:9425a9e2e5c80570d7b3642bed78f5c48c244e4c63e417abf9a8811a9ba90381>
    prez:searchResultPredicate <urn:jena:lucene:field#title> ;
    prez:searchResultMatch "CAD-DDH-001 Cadia Deep Exploration Hole" ;
    a prez:SearchResultMatch .
<urn:facet:e8e6e61a91e60a42f594395130eaee4cb5ca9e67fff6e08594fe5aa34a881685> prez:facetValue <http://example.org/mining/commodity/Gold> ;
    prez:facetName <urn:jena:lucene:field#commodity> ;
    prez:facetCount 2 .
<urn:facet:9f9f76c45f67d42926169c094038f4eb0df4fd202abac4a4cee29b8be0d2812e> prez:facetValue <http://example.org/mining/commodity/Copper> ;
    prez:facetName <urn:jena:lucene:field#commodity> ;
    prez:facetCount 1 .
<urn:facet:dae674b26007084e26ca0b99f2d009ee605511185a3909b7baaa946883a55bdb> prez:facetValue <http://example.org/mining/state/NSW> ;
    prez:facetName <urn:jena:lucene:field#state> ;
    prez:facetCount 1 .
<urn:facet:9b6ef4971a241d02389b4882a8140bc1a324c75855d8b2a8d4cf0373d6a157d5> prez:facetValue <http://example.org/mining/state/WA> ;
    prez:facetName <urn:jena:lucene:field#state> ;
    prez:facetCount 1 .
"""
EXPECTED_COPPER_TURTLE = """\
@prefix altr-ext: <http://www.w3.org/ns/dx/connegp/altr-ext#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix shext: <http://example.com/shacl-extension#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix prof: <http://www.w3.org/ns/dx/prof/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex1: <http://example.org/mining/> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prfl: <https://w3id.org/profile/> .
@prefix profile: <https://prez.dev/profile/> .
@prefix exm: <https://example.com/> .
@prefix ex: <http://example.org/> .
@prefix prez: <https://prez.dev/> .
ex1:bh-cad-001 a ex1:Borehole .
prez:SearchResult prez:count 1 .
<urn:hash:320eea1fc6c09ca1264e45d769e97d5c5dbeaafbb66a58f7ce0e0d5b89d7ca00> prez:searchResultWeight "3.175807"^^xsd:float ;
    prez:searchResultURI ex1:bh-cad-001 ;
    prez:hasSearchMatch <urn:match:320eea1fc6c09ca1264e45d769e97d5c5dbeaafbb66a58f7ce0e0d5b89d7ca00> ;
    a prez:SearchResult .
<urn:match:320eea1fc6c09ca1264e45d769e97d5c5dbeaafbb66a58f7ce0e0d5b89d7ca00>
    prez:searchResultPredicate <urn:jena:lucene:field#title> ;
    prez:searchResultMatch "CAD-DDH-001 Cadia Deep Exploration Hole" ;
    a prez:SearchResultMatch .
<urn:facet:9f9f76c45f67d42926169c094038f4eb0df4fd202abac4a4cee29b8be0d2812e> prez:facetValue <http://example.org/mining/commodity/Copper> ;
    prez:facetName <urn:jena:lucene:field#commodity> ;
    prez:facetCount 1 .
<urn:facet:23e7ef3733003036814ee05a41611e03e34c131393bd5430c7d4ad7a66df4abf> prez:facetValue <http://example.org/mining/commodity/Gold> ;
    prez:facetName <urn:jena:lucene:field#commodity> ;
    prez:facetCount 1 .
<urn:facet:dae674b26007084e26ca0b99f2d009ee605511185a3909b7baaa946883a55bdb> prez:facetValue <http://example.org/mining/state/NSW> ;
    prez:facetName <urn:jena:lucene:field#state> ;
    prez:facetCount 1 .
"""


def _wait_for_fuseki_ready(query_url: str) -> None:
    params = {"query": "ASK {}"}
    timeout = 30
    for _ in range(timeout):
        try:
            response = httpx.get(query_url, params=params, timeout=5)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        sleep(1)
    raise RuntimeError(f"Fuseki did not become ready at {query_url}")


def _seed_dataset(data_url: str, dataset_files: list[Path]) -> None:
    merged_graph = Graph()
    for dataset_file in dataset_files:
        merged_graph.parse(dataset_file, format="turtle")
    response = httpx.put(
        data_url,
        params={"default": ""},
        content=merged_graph.serialize(format="turtle"),
        headers={"Content-Type": "text/turtle"},
        timeout=30,
    )
    response.raise_for_status()


def _normalize_dynamic_nodes(graph: Graph) -> Graph:
    normalized = Graph()
    node_map: dict[URIRef, BNode] = {}

    def _map_node(node):
        if isinstance(node, URIRef) and (
            str(node).startswith("urn:hash:")
            or str(node).startswith("urn:match:")
            or str(node).startswith("urn:facet:")
        ):
            if node not in node_map:
                node_map[node] = BNode()
            return node_map[node]
        return node

    for subject, predicate, obj in graph:
        normalized.add((_map_node(subject), predicate, _map_node(obj)))
    return normalized


def _assert_graph_isomorphic(actual_graph: Graph, expected_graph: Graph) -> None:
    actual_iso = to_isomorphic(_normalize_dynamic_nodes(actual_graph))
    expected_iso = to_isomorphic(_normalize_dynamic_nodes(expected_graph))
    if actual_iso == expected_iso:
        return
    both, actual_only, expected_only = graph_diff(actual_iso, expected_iso)
    raise AssertionError(
        "Response graph was not isomorphic to expected graph.\n"
        f"Shared:\n{both.serialize(format='turtle')}\n"
        f"Actual only:\n{actual_only.serialize(format='turtle')}\n"
        f"Expected only:\n{expected_only.serialize(format='turtle')}"
    )


def _expected_graph(expected_turtle: str) -> Graph:
    return Graph().parse(data=expected_turtle, format="turtle")


def _stream_turtle_response(client: TestClient, params: list[tuple[str, str]]) -> Graph:
    with client.stream("GET", "/cql", params=params) as response:
        assert response.status_code == 200
        body = b"".join(response.iter_bytes())
        headers = dict(response.headers)

    if headers.get("content-encoding") == "gzip":
        body = gzip.decompress(body)

    return Graph().parse(data=body.decode("utf-8"), format="turtle")


@contextmanager
def _patched_runtime_settings(local_settings: Settings):
    patched_keys = (
        "enable_cql_jena_lucene_json",
        "jena_fuseki_dataset_name",
        "jena_assembler_path",
        "lucene_default_limit",
        "lucene_index_name",
        "sparql_repo_type",
        "sparql_endpoint",
        "enable_sparql_endpoint",
    )
    original_values = {key: getattr(global_settings, key) for key in patched_keys}
    try:
        for key in patched_keys:
            setattr(global_settings, key, getattr(local_settings, key))
        yield
    finally:
        for key, value in original_values.items():
            setattr(global_settings, key, value)


@pytest.fixture(scope="session")
def fuseki_container() -> DockerContainer:
    image = DockerImage(
        path=str(DOCKERFILE_DIR),
        tag=IMAGE_TAG,
        dockerfile_path="Dockerfile",
    )
    image.build()

    container = DockerContainer(IMAGE_TAG).with_exposed_ports(3030)
    try:
        container.start()
        host = container.get_container_host_ip()
        port = container.get_exposed_port(3030)
        query_url = f"http://{host}:{port}/mining/query"
        data_url = f"http://{host}:{port}/mining/data"
        _wait_for_fuseki_ready(query_url)
        _seed_dataset(
            data_url,
            [
                DATA_DIR / "mining.ttl",
                DATA_DIR / "generated.ttl",
            ],
        )
        yield container
    finally:
        container.stop()
        image.remove()


@pytest.fixture(scope="session")
def lucene_client(fuseki_container: DockerContainer) -> TestClient:
    host = fuseki_container.get_container_host_ip()
    port = fuseki_container.get_exposed_port(3030)
    local_settings = Settings(
        enable_cql_jena_lucene_json=True,
        jena_fuseki_dataset_name="mining",
        jena_assembler_path=str(CONFIG_PATH),
        lucene_default_limit=10000,
        lucene_index_name="default",
        sparql_repo_type="remote",
        sparql_endpoint=f"http://{host}:{port}/mining/query",
        enable_sparql_endpoint=False,
    )

    with _patched_runtime_settings(local_settings):
        app = assemble_app(local_settings=local_settings)
        with TestClient(app) as client:
            yield client


@pytest.mark.skip(reason="requires Docker / testcontainers — run manually")
@pytest.mark.parametrize(
    ("commodity_iri", "expected_turtle"),
    [
        ("http://example.org/mining/commodity/Gold", EXPECTED_GOLD_TURTLE),
        ("http://example.org/mining/commodity/Copper", EXPECTED_COPPER_TURTLE),
    ],
)
def test_lucene_cql_response_isomorphic_to_expected_graph(
    lucene_client: TestClient,
    commodity_iri: str,
    expected_turtle: str,
):
    actual_graph = _stream_turtle_response(
        lucene_client,
        [
            ("q", "deep"),
            (
                "filter",
                f'{{"op":"=","args":[{{"property":"urn:jena:lucene:field#commodity"}},"{commodity_iri}"]}}',
            ),
            ("facets", "urn:jena:lucene:field#commodity"),
            ("facets", "urn:jena:lucene:field#state"),
            ("_mediatype", "text/turtle"),
        ],
    )
    _assert_graph_isomorphic(actual_graph, _expected_graph(expected_turtle))
