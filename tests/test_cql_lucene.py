import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import RdfFormat, Store
from rdflib import Graph

from prez.app import assemble_app
from prez.config import Settings
from prez.dependencies import get_data_repo, get_system_repo
from prez.repositories import PyoxigraphRepo, Repo
from prez.routers.cql_lucene_router import router as cql_lucene_router
from prez.services.query_generation.cql_lucene_json import (
    generate_cql_lucene_json_sparql,
)


class FakeLuceneRepo(Repo):
    def __init__(self):
        self.queries = []

    async def rdf_query_to_rdflib_graph(self, query: str, into_graph: Graph | None = None):
        raise NotImplementedError

    async def rdf_query_to_oxigraph_store(self, query: str, into_store=None):
        raise NotImplementedError

    async def tabular_query_to_table(self, query: str, context=None):
        raise NotImplementedError

    async def sparql(self, query: str, raw_headers, method: str = "GET"):
        self.queries.append(
            {
                "query": query,
                "raw_headers": raw_headers,
                "method": method,
            }
        )
        return {"head": {"vars": []}, "results": {"bindings": []}}


def _build_lucene_test_client():
    app = FastAPI()
    app.state.settings = Settings(
        enable_cql_jena_lucene_json=True,
        jena_fuseki_dataset_name="dataset",
        lucene_default_limit=77,
        lucene_index_name="default",
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )
    app.include_router(cql_lucene_router)

    system_store = Store()
    system_store.load(
        """
        @prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
        @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix prez: <https://prez.dev/ont/> .

        <file:///fuseki/config.ttl#field-commodity>
            a cql:Queryable ;
            dcterms:identifier "file:///fuseki/config.ttl#field-commodity" ;
            prez:facetable true .

        <file:///fuseki/config.ttl#field-state>
            a cql:Queryable ;
            dcterms:identifier "file:///fuseki/config.ttl#field-state" ;
            prez:facetable true .

        <file:///fuseki/config.ttl#field-hidden>
            a cql:Queryable ;
            dcterms:identifier "file:///fuseki/config.ttl#field-hidden" .
        """.encode("utf-8"),
        RdfFormat.TURTLE,
    )

    fake_repo = FakeLuceneRepo()
    app.dependency_overrides[get_data_repo] = lambda: fake_repo
    app.dependency_overrides[get_system_repo] = lambda: PyoxigraphRepo(system_store)
    return TestClient(app), fake_repo


def _escaped_sparql_json_string(value) -> str:
    compact_json = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(compact_json, ensure_ascii=False)


def _cql_route_modules(app):
    return {
        (route.path, tuple(sorted(route.methods))): route.endpoint.__module__
        for route in app.routes
        if route.path == "/cql"
    }


def test_lucene_feature_flag_requires_dataset_name():
    with pytest.raises(ValueError, match="jena_fuseki_dataset_name"):
        Settings(
            enable_cql_jena_lucene_json=True,
            sparql_repo_type="remote",
            sparql_endpoint="http://example.com/dataset/sparql",
        )


def test_lucene_feature_flag_requires_remote_repo():
    with pytest.raises(ValueError, match="sparql_repo_type=remote"):
        Settings(
            enable_cql_jena_lucene_json=True,
            sparql_repo_type="pyoxigraph_memory",
            jena_fuseki_dataset_name="dataset",
        )


def test_lucene_default_limit_must_be_positive():
    with pytest.raises(ValueError, match="lucene_default_limit"):
        Settings(lucene_default_limit=0)


def test_lucene_index_name_must_be_non_empty():
    with pytest.raises(ValueError, match="lucene_index_name"):
        Settings(lucene_index_name="  ")


def test_cql_router_registration_defaults_to_legacy_router():
    app = assemble_app(local_settings=Settings())
    cql_routes = _cql_route_modules(app)
    assert cql_routes[("/cql", ("GET",))] == "prez.routers.cql_router"
    assert cql_routes[("/cql", ("POST",))] == "prez.routers.cql_router"


def test_cql_router_registration_switches_to_lucene_router():
    app = assemble_app(
        local_settings=Settings(
            enable_cql_jena_lucene_json=True,
            jena_fuseki_dataset_name="dataset",
            sparql_repo_type="remote",
            sparql_endpoint="http://example.com/dataset/sparql",
        )
    )
    cql_routes = _cql_route_modules(app)
    assert cql_routes[("/cql", ("GET",))] == "prez.routers.cql_lucene_router"
    assert cql_routes[("/cql", ("POST",))] == "prez.routers.cql_lucene_router"


def test_generate_cql_lucene_json_sparql_defaults_q_to_wildcard():
    query = generate_cql_lucene_json_sparql(
        lucene_index_name="default",
        q=None,
        filter_json=None,
        facets=None,
        limit=100,
        offset=5,
    )
    assert 'luc:query ( "default" "*" 100 )' in query
    assert "LIMIT 100" in query
    assert "OFFSET 5" in query


def test_generate_cql_lucene_json_sparql_omits_lucene_facet_when_not_requested():
    filter_json = {"op": "=", "args": [{"property": "http://example.com/p"}, "x"]}
    query = generate_cql_lucene_json_sparql(
        lucene_index_name="default",
        q="ore",
        filter_json=filter_json,
        facets=None,
        limit=10,
        offset=0,
    )
    assert "luc:facet" not in query
    assert _escaped_sparql_json_string(filter_json) in query


def test_generate_cql_lucene_json_sparql_includes_facets_as_json_array():
    facets = [
        "file:///fuseki/config.ttl#field-commodity",
        "file:///fuseki/config.ttl#field-state",
    ]
    query = generate_cql_lucene_json_sparql(
        lucene_index_name="default",
        q="ore",
        filter_json=None,
        facets=facets,
        limit=10,
        offset=0,
    )
    assert "luc:facet" in query
    assert _escaped_sparql_json_string(facets) in query
    assert 'luc:facet ( "default" "ore"' in query


def test_generate_cql_lucene_json_sparql_uses_configured_index_name():
    query = generate_cql_lucene_json_sparql(
        lucene_index_name="custom-index",
        q="ore",
        filter_json=None,
        facets=["file:///fuseki/config.ttl#field-commodity"],
        limit=10,
        offset=0,
    )
    assert 'luc:query ( "custom-index" "ore" 10 )' in query
    assert 'luc:facet ( "custom-index" "ore"' in query


def test_lucene_cql_get_defaults_q_and_returns_sparql_results_json():
    client, fake_repo = _build_lucene_test_client()
    try:
        response = client.get("/cql")
    finally:
        client.close()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-results+json")
    assert fake_repo.queries[-1]["method"] == "POST"
    assert fake_repo.queries[-1]["raw_headers"] == [
        (b"accept", b"application/sparql-results+json")
    ]
    assert 'luc:query ( "default" "*" 77 )' in fake_repo.queries[-1]["query"]


def test_lucene_cql_get_accepts_filter_only():
    client, fake_repo = _build_lucene_test_client()
    filter_json = {"op": "=", "args": [{"property": "http://example.com/p"}, "x"]}
    try:
        response = client.get("/cql", params={"filter": json.dumps(filter_json)})
    finally:
        client.close()

    assert response.status_code == 200
    assert _escaped_sparql_json_string(filter_json) in fake_repo.queries[-1]["query"]
    assert "luc:facet" not in fake_repo.queries[-1]["query"]


def test_lucene_cql_get_accepts_repeated_facets():
    client, fake_repo = _build_lucene_test_client()
    facets = [
        "file:///fuseki/config.ttl#field-commodity",
        "file:///fuseki/config.ttl#field-state",
    ]
    try:
        response = client.get(
            "/cql",
            params=[
                ("facets", facets[0]),
                ("facets", facets[1]),
            ],
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert "luc:facet" in fake_repo.queries[-1]["query"]
    assert _escaped_sparql_json_string(facets) in fake_repo.queries[-1]["query"]


def test_lucene_cql_get_accepts_q_filter_facets_limit_and_offset():
    client, fake_repo = _build_lucene_test_client()
    filter_json = {"op": "=", "args": [{"property": "http://example.com/p"}, "x"]}
    facets = [
        "file:///fuseki/config.ttl#field-commodity",
        "file:///fuseki/config.ttl#field-state",
    ]
    try:
        response = client.get(
            "/cql",
            params=[
                ("q", "ore"),
                ("filter", json.dumps(filter_json)),
                ("facets", facets[0]),
                ("facets", facets[1]),
                ("limit", "5"),
                ("offset", "10"),
            ],
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-results+json")
    assert 'luc:query ( "default" "ore" "{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"http://example.com/p\\"},\\"x\\"]}" 5 )' in fake_repo.queries[-1]["query"]
    assert 'luc:facet ( "default" "ore" "[\\"file:///fuseki/config.ttl#field-commodity\\",\\"file:///fuseki/config.ttl#field-state\\"]" "{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"http://example.com/p\\"},\\"x\\"]}" 5 )' in fake_repo.queries[-1]["query"]
    assert "LIMIT 5" in fake_repo.queries[-1]["query"]
    assert "OFFSET 10" in fake_repo.queries[-1]["query"]


def test_lucene_cql_get_rejects_invalid_facet():
    client, _ = _build_lucene_test_client()
    try:
        response = client.get(
            "/cql",
            params={"facets": "file:///fuseki/config.ttl#field-hidden"},
        )
    finally:
        client.close()

    assert response.status_code == 400
    assert "Unsupported facet IRIs" in response.json()["detail"]
    assert "file:///fuseki/config.ttl#field-hidden" in response.json()["detail"]


def test_lucene_cql_get_rejects_non_iri_property():
    client, _ = _build_lucene_test_client()
    try:
        response = client.get(
            "/cql",
            params={
                "filter": json.dumps(
                    {"op": "=", "args": [{"property": "not-an-iri"}, "x"]}
                )
            },
        )
    finally:
        client.close()

    assert response.status_code == 400
    assert "CQL property values must be IRIs" in response.json()["detail"]


def test_lucene_cql_post_accepts_q_filter_facets_limit_and_offset():
    client, fake_repo = _build_lucene_test_client()
    try:
        response = client.post(
            "/cql",
            json={
                "q": "ore",
                "filter": {"op": "=", "args": [{"property": "http://example.com/p"}, "x"]},
                "facets": ["file:///fuseki/config.ttl#field-commodity"],
                "limit": 5,
                "offset": 10,
                "_mediatype": "text/turtle",
                "_profile": "ignored",
            },
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-results+json")
    assert 'luc:query ( "default" "ore" "{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"http://example.com/p\\"},\\"x\\"]}" 5 )' in fake_repo.queries[-1]["query"]
    assert 'luc:facet ( "default" "ore" "[\\"file:///fuseki/config.ttl#field-commodity\\"]" "{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"http://example.com/p\\"},\\"x\\"]}" 5 )' in fake_repo.queries[-1]["query"]
    assert "LIMIT 5" in fake_repo.queries[-1]["query"]
    assert "OFFSET 10" in fake_repo.queries[-1]["query"]


def test_lucene_cql_route_uses_configured_index_name():
    app = FastAPI()
    app.state.settings = Settings(
        enable_cql_jena_lucene_json=True,
        jena_fuseki_dataset_name="dataset",
        lucene_default_limit=77,
        lucene_index_name="custom-index",
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )
    app.include_router(cql_lucene_router)

    system_store = Store()
    fake_repo = FakeLuceneRepo()
    app.dependency_overrides[get_data_repo] = lambda: fake_repo
    app.dependency_overrides[get_system_repo] = lambda: PyoxigraphRepo(system_store)

    with TestClient(app) as client:
        response = client.get("/cql")

    assert response.status_code == 200
    assert 'luc:query ( "custom-index" "*" 77 )' in fake_repo.queries[-1]["query"]


def test_lucene_cql_post_rejects_non_object_filter():
    client, _ = _build_lucene_test_client()
    try:
        response = client.post("/cql", json={"filter": []})
    finally:
        client.close()

    assert response.status_code == 400
    assert response.json()["detail"] == "POST filter must be a JSON object."


def test_lucene_cql_post_rejects_invalid_facets_shape():
    client, _ = _build_lucene_test_client()
    try:
        response = client.post("/cql", json={"facets": "not-an-array"})
    finally:
        client.close()

    assert response.status_code == 400
    assert response.json()["detail"] == "POST facets must be an array of IRI strings."


def test_lucene_cql_rejects_invalid_limit_and_offset():
    client, _ = _build_lucene_test_client()
    try:
        response_limit = client.get("/cql", params={"limit": 0})
        response_offset = client.post("/cql", json={"offset": -1})
    finally:
        client.close()

    assert response_limit.status_code == 400
    assert response_limit.json()["detail"] == "limit must be a positive integer."
    assert response_offset.status_code == 400
    assert response_offset.json()["detail"] == "offset must be a non-negative integer."
