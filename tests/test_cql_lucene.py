import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pyoxigraph import Store, DefaultGraph, NamedNode, Literal, Quad
from rdflib import Graph, RDF, Literal as RDFLiteral, URIRef
from sparql_grammar_pydantic import Var

from prez.app import assemble_app
from prez.config import Settings, settings as global_settings
from prez.dependencies import (
    generate_concept_hierarchy_query,
    get_data_repo,
    get_endpoint_nodeshapes,
    get_endpoint_structure,
    get_endpoint_structure_listing_post,
    get_negotiated_pmts,
    get_negotiated_pmts_listing_post,
    get_profile_nodeshape,
    get_profile_nodeshape_listing_post,
    get_system_repo,
    get_url,
)
from prez.repositories import Repo
from prez.reference_data.prez_ns import ONT, PREZ
from prez.routers.cql_lucene_router import router as cql_lucene_router
from prez.services.query_generation.search_jena_lucene import LuceneFacetQuery, SearchQueryJenaLucene


class FakeLuceneListingRepo(Repo):
    def __init__(self):
        self.rdf_queries: list[list[str]] = []
        self.tabular_queries: list[list] = []
        self.return_oxigraph_store_flags: list[bool] = []

    def _build_result_store(self) -> Store:
        store = Store()
        default = DefaultGraph()
        focus_node = NamedNode("http://example.com/resource/1")
        hash_node = NamedNode("urn:hash:1")
        store.add(Quad(focus_node, NamedNode(str(PREZ.type)), NamedNode(str(PREZ.FocusNode)), default))
        store.add(Quad(focus_node, NamedNode(str(RDF.type)), NamedNode("http://example.com/Class"), default))
        store.add(Quad(hash_node, NamedNode(str(RDF.type)), NamedNode(str(PREZ.SearchResult)), default))
        store.add(Quad(hash_node, NamedNode(str(PREZ.searchResultURI)), focus_node, default))
        store.add(Quad(hash_node, NamedNode(str(PREZ.searchResultMatch)), Literal("deep"), default))
        store.add(
            Quad(
                hash_node,
                NamedNode(str(PREZ.searchResultPredicate)),
                NamedNode("urn:jena:lucene:field#commodity"),
                default,
            )
        )
        store.add(Quad(hash_node, NamedNode(str(PREZ.searchResultWeight)), Literal("1"), default))
        store.add(
            Quad(
                NamedNode(str(PREZ.SearchResult)),
                NamedNode(str(PREZ["count"])),
                Literal("2"),
                default,
            )
        )
        return store

    async def send_queries(
        self,
        rdf_queries,
        tabular_queries=[],
        return_oxigraph_store=False,
    ):
        self.rdf_queries.append(rdf_queries)
        self.tabular_queries.append(tabular_queries)
        self.return_oxigraph_store_flags.append(return_oxigraph_store)
        if return_oxigraph_store:
            store = self._build_result_store()
            default = DefaultGraph()
            if any("urn:jena:lucene:index#facet" in query for query in rdf_queries):
                facet_node = NamedNode("urn:facet:1")
                store.add(Quad(facet_node, NamedNode(str(PREZ.facetName)), NamedNode("urn:jena:lucene:field#commodity"), default))
                store.add(Quad(facet_node, NamedNode(str(PREZ.facetValue)), Literal("Gold"), default))
                store.add(Quad(facet_node, NamedNode(str(PREZ.facetCount)), Literal("2"), default))
            return store, []
        return Graph(), []

    async def rdf_query_to_rdflib_graph(self, query: str, into_graph: Graph | None = None):
        graph = into_graph if into_graph is not None else Graph()
        commodity = URIRef("urn:jena:lucene:field#commodity")
        state = URIRef("urn:jena:lucene:field#state")
        graph.add((commodity, URIRef(str(ONT.facetable)), RDFLiteral(True)))
        graph.add((state, URIRef(str(ONT.facetable)), RDFLiteral(True)))
        return graph

    async def rdf_query_to_oxigraph_store(self, query: str, into_store=None):
        raise NotImplementedError

    async def tabular_query_to_table(self, query: str, context=None):
        raise NotImplementedError

    async def sparql(self, query: str, raw_headers: list[tuple[bytes, bytes]], method: str = "GET"):
        raise NotImplementedError


@contextmanager
def _build_lucene_test_client(
    test_repo: Repo | None,
    *,
    lucene_index_name: str = "default",
) -> TestClient:
    local_settings = Settings(
        enable_cql_jena_lucene_json=True,
        jena_fuseki_dataset_name="dataset",
        lucene_default_limit=77,
        lucene_index_name=lucene_index_name,
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )
    original_values = {
        key: getattr(global_settings, key)
        for key in (
            "enable_cql_jena_lucene_json",
            "jena_fuseki_dataset_name",
            "lucene_default_limit",
            "lucene_index_name",
            "sparql_repo_type",
            "sparql_endpoint",
        )
    }
    for key, value in original_values.items():
        setattr(global_settings, key, getattr(local_settings, key))
    app = FastAPI()
    app.state.settings = local_settings
    app.include_router(cql_lucene_router)

    fake_endpoint_nodeshape = SimpleNamespace(
        uri="http://example.org/ns#CQL",
        targetClasses=[],
        tssp_list=[],
        gpnt_list=[],
        tssp_exists_list=[],
        gpnt_exists_list=[],
    )
    fake_profile_nodeshape = SimpleNamespace(
        uri="http://example.org/profile",
        focus_node=Var(value="focus_node"),
        tss_list=[],
        tssp_list=[],
        gpnt_list=[],
    )

    class FakePMTs:
        def __init__(self, mediatype: str):
            self.selected = {
                "mediatype": mediatype,
                "profile": "http://example.org/profile",
                "class": URIRef("http://example.com/Class"),
            }
            self.requested_mediatypes = (
                [(mediatype, 1.0)] if mediatype == "application/sparql-query" else None
            )

        def generate_response_headers(self):
            return {}

    async def _get_fake_pmts(request: Request):
        mediatype = request.query_params.get("_mediatype", "text/turtle")
        return FakePMTs(mediatype)

    async def _get_fake_pmts_post(request: Request):
        body = await request.json()
        mediatype = body.get("_mediatype", "text/turtle") if isinstance(body, dict) else "text/turtle"
        return FakePMTs(mediatype)

    app.dependency_overrides[get_data_repo] = lambda: test_repo
    app.dependency_overrides[get_system_repo] = lambda: test_repo
    app.dependency_overrides[get_endpoint_nodeshapes] = lambda: fake_endpoint_nodeshape
    app.dependency_overrides[get_profile_nodeshape] = lambda: fake_profile_nodeshape
    app.dependency_overrides[get_profile_nodeshape_listing_post] = (
        lambda: fake_profile_nodeshape
    )
    app.dependency_overrides[get_negotiated_pmts] = _get_fake_pmts
    app.dependency_overrides[get_negotiated_pmts_listing_post] = _get_fake_pmts_post
    app.dependency_overrides[get_endpoint_structure] = lambda: tuple()
    app.dependency_overrides[get_endpoint_structure_listing_post] = lambda: tuple()
    app.dependency_overrides[generate_concept_hierarchy_query] = lambda: None
    app.dependency_overrides[get_url] = lambda: "http://testserver/cql"
    try:
        with TestClient(app) as client:
            yield client
    finally:
        for key, value in original_values.items():
            setattr(global_settings, key, value)


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


def test_search_query_jena_lucene_defaults_q_to_wildcard():
    search_query = SearchQueryJenaLucene(
        term=None,
        limit=100,
        offset=5,
        lucene_index_name="default",
    )

    query_fragment = search_query.valid_lucene_query_triple

    assert "urn:jena:lucene:index#query" in query_fragment
    assert "(?focus_node ?weight ?match ?totalHits ?g ?pred)" in query_fragment
    assert '("default" "*" 106)' in query_fragment
    assert search_query.limit == 101


def test_search_query_jena_lucene_includes_compact_filter_json():
    filter_json = {
        "op": "=",
        "args": [{"property": "http://example.com/predicate"}, "Gold"],
    }
    search_query = SearchQueryJenaLucene(
        term="ore",
        filter_json=filter_json,
        limit=5,
        offset=10,
        lucene_index_name="custom-index",
    )

    query_fragment = search_query.valid_lucene_query_triple

    assert "(?focus_node ?weight ?match ?totalHits ?g ?pred)" in query_fragment
    assert '("custom-index" "ore"' in query_fragment
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"http://example.com/predicate\\"},\\"Gold\\"]}"'
        in query_fragment
    )
    assert query_fragment.endswith("16) .")


def test_lucene_facet_query_serializes_requested_facets():
    facet_query = LuceneFacetQuery(
        term="deep",
        facets=[
            "urn:jena:lucene:field#commodity",
            "urn:jena:lucene:field#state",
        ],
        filter_json={
            "op": "=",
            "args": [{"property": "urn:jena:lucene:field#commodity"}, "Gold"],
        },
        limit=10,
        lucene_index_name="default",
    )

    query_string = facet_query.to_string()

    assert "urn:jena:lucene:index#facet" in query_string
    assert "<https://prez.dev/facetName> ?facetName" in query_string
    assert (
        '"[\\"urn:jena:lucene:field#commodity\\",\\"urn:jena:lucene:field#state\\"]"'
        in query_string
    )
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"'
        in query_string
    )
    assert '("default" "deep"' in query_string


def test_lucene_cql_get_supports_conneg_and_uses_default_limit(test_repo: Repo):
    with _build_lucene_test_client(test_repo) as client:
        response = client.get("/cql", params={"_mediatype": "application/sparql-query"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-query")
    assert "CONSTRUCT" in response.text
    assert "urn:jena:lucene:index#query" in response.text
    assert "(?focus_node ?weight ?match ?totalHits ?g ?pred)" in response.text
    assert "<https://prez.dev/count> ?totalHits" in response.text
    assert '("default" "*" 78)' in response.text
    assert "LIMIT 78" in response.text


def test_lucene_cql_get_accepts_q_filter_limit_and_offset(test_repo: Repo):
    with _build_lucene_test_client(test_repo, lucene_index_name="custom-index") as client:
        response = client.get(
            "/cql",
            params={
                "_mediatype": "application/sparql-query",
                "q": "ore",
                "filter": json.dumps(
                    {
                        "op": "=",
                        "args": [
                            {"property": "urn:jena:lucene:field#commodity"},
                            "Gold",
                        ],
                    }
                ),
                "limit": "5",
                "offset": "10",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-query")
    assert "urn:jena:lucene:index#query" in response.text
    assert "(?focus_node ?weight ?match ?totalHits ?g ?pred)" in response.text
    assert "<https://prez.dev/count> ?totalHits" in response.text
    assert '("custom-index" "ore"' in response.text
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"'
        in response.text
    )
    assert "LIMIT 6" in response.text
    assert "OFFSET 10" in response.text
    assert " 16)" in response.text


def test_lucene_cql_post_accepts_q_filter_limit_and_offset(test_repo: Repo):
    with _build_lucene_test_client(test_repo) as client:
        response = client.post(
            "/cql",
            json={
                "_mediatype": "application/sparql-query",
                "q": "ore",
                "filter": {
                    "op": "=",
                    "args": [
                        {"property": "urn:jena:lucene:field#commodity"},
                        "Gold",
                    ],
                },
                "limit": 5,
                "offset": 10,
                "_profile": "ignored-by-negotiation",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-query")
    assert "urn:jena:lucene:index#query" in response.text
    assert "(?focus_node ?weight ?match ?totalHits ?g ?pred)" in response.text
    assert "<https://prez.dev/count> ?totalHits" in response.text
    assert '("default" "ore"' in response.text
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"'
        in response.text
    )
    assert "LIMIT 6" in response.text
    assert "OFFSET 10" in response.text
    assert " 16)" in response.text


def test_lucene_cql_get_renders_successfully_via_listing_pipeline():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.get(
            "/cql",
            params={
                "q": "deep",
                "filter": json.dumps(
                    {
                        "op": "=",
                        "args": [
                            {"property": "urn:jena:lucene:field#commodity"},
                            "Gold",
                        ],
                    }
                ),
                "_mediatype": "text/turtle",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/turtle")
    assert fake_repo.return_oxigraph_store_flags == [True]
    assert "urn:jena:lucene:index#query" in fake_repo.rdf_queries[0][0]
    assert "(?focus_node ?weight ?match ?totalHits ?g ?pred)" in fake_repo.rdf_queries[0][0]
    assert '("default" "deep"' in fake_repo.rdf_queries[0][0]
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"'
        in fake_repo.rdf_queries[0][0]
    )
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert (
        URIRef("urn:hash:1"),
        RDF.type,
        URIRef(str(PREZ.SearchResult)),
    ) in rendered_graph
    assert (
        URIRef("urn:hash:1"),
        URIRef(str(PREZ.searchResultWeight)),
        None,
    ) in rendered_graph
    assert (
        URIRef(str(PREZ.SearchResult)),
        URIRef(str(PREZ["count"])),
        None,
    ) in rendered_graph


def test_lucene_cql_post_renders_successfully_via_listing_pipeline():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.post(
            "/cql",
            json={
                "q": "deep",
                "filter": {
                    "op": "=",
                    "args": [
                        {"property": "urn:jena:lucene:field#commodity"},
                        "Gold",
                    ],
                },
                "_mediatype": "text/turtle",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/turtle")
    assert fake_repo.return_oxigraph_store_flags == [True]
    assert "urn:jena:lucene:index#query" in fake_repo.rdf_queries[0][0]
    assert "(?focus_node ?weight ?match ?totalHits ?g ?pred)" in fake_repo.rdf_queries[0][0]
    assert '("default" "deep"' in fake_repo.rdf_queries[0][0]
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"'
        in fake_repo.rdf_queries[0][0]
    )
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert (
        URIRef("http://example.com/resource/1"),
        URIRef(str(PREZ.type)),
        URIRef(str(PREZ.FocusNode)),
    ) in rendered_graph
    assert (
        URIRef("urn:hash:1"),
        URIRef(str(PREZ.searchResultWeight)),
        None,
    ) in rendered_graph
    assert (
        URIRef(str(PREZ.SearchResult)),
        URIRef(str(PREZ["count"])),
        None,
    ) in rendered_graph


def test_lucene_cql_get_rendered_path_uses_wildcard_and_default_limit():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.get("/cql", params={"_mediatype": "text/turtle"})

    assert response.status_code == 200
    assert fake_repo.return_oxigraph_store_flags == [True]
    assert '("default" "*" 78)' in fake_repo.rdf_queries[0][0]


def test_lucene_cql_get_with_facet_profile_appends_facets_query():
    fake_repo = FakeLuceneListingRepo()
    fake_facets_query = SimpleNamespace(to_string=lambda: "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")

    with patch(
        "prez.services.listings.FacetQuery.create_facets_query",
        return_value=("http://example.com/facet-profile", fake_facets_query),
    ):
        with _build_lucene_test_client(fake_repo) as client:
            response = client.get(
                "/cql",
                params={
                    "_mediatype": "text/turtle",
                    "facet_profile": "http://example.com/facet-profile",
                },
            )

    assert response.status_code == 200
    assert len(fake_repo.rdf_queries[0]) == 2
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert any(
        obj == URIRef("http://example.com/facet-profile")
        for _, _, obj in rendered_graph.triples((None, URIRef(str(PREZ.facetProfile)), None))
    )


def test_lucene_cql_sparql_query_response_includes_all_generated_queries():
    with _build_lucene_test_client(FakeLuceneListingRepo()) as client:
        response = client.post(
            "/cql",
            json={
                "_mediatype": "application/sparql-query",
                "q": "deep",
                "filter": {
                    "op": "=",
                    "args": [
                        {"property": "urn:jena:lucene:field#commodity"},
                        "Gold",
                    ],
                },
                "facets": [
                    "urn:jena:lucene:field#commodity",
                    "urn:jena:lucene:field#state",
                ],
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-query")
    assert "# Query 1" in response.text
    assert "# Query 2" in response.text
    assert "urn:jena:lucene:index#query" in response.text
    assert "urn:jena:lucene:index#facet" in response.text


def test_lucene_cql_get_accepts_facets_and_appends_lucene_facet_query():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.get(
            "/cql",
            params={
                "_mediatype": "text/turtle",
                "facets": [
                    "urn:jena:lucene:field#commodity",
                    "urn:jena:lucene:field#state",
                ],
            },
        )

    assert response.status_code == 200
    assert len(fake_repo.rdf_queries[0]) == 2
    assert "urn:jena:lucene:index#facet" in fake_repo.rdf_queries[0][1]
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert (
        None,
        URIRef(str(PREZ.facetName)),
        URIRef("urn:jena:lucene:field#commodity"),
    ) in rendered_graph


def test_lucene_cql_post_accepts_facets_and_appends_lucene_facet_query():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.post(
            "/cql",
            json={
                "_mediatype": "text/turtle",
                "facets": [
                    "urn:jena:lucene:field#commodity",
                    "urn:jena:lucene:field#state",
                ],
            },
        )

    assert response.status_code == 200
    assert len(fake_repo.rdf_queries[0]) == 2
    assert "urn:jena:lucene:index#facet" in fake_repo.rdf_queries[0][1]


def test_lucene_cql_get_rejects_non_object_filter(test_repo: Repo):
    with _build_lucene_test_client(test_repo) as client:
        response = client.get("/cql", params={"filter": json.dumps(["not-an-object"])})

    assert response.status_code == 400
    assert response.json()["detail"] == "GET filter must be a JSON object."


def test_lucene_cql_post_rejects_non_object_filter(test_repo: Repo):
    with _build_lucene_test_client(test_repo) as client:
        response = client.post("/cql", json={"filter": ["not-an-object"]})

    assert response.status_code == 400
    assert response.json()["detail"] == "POST filter must be a JSON object."


def test_lucene_cql_get_rejects_non_iri_property(test_repo: Repo):
    with _build_lucene_test_client(test_repo) as client:
        response = client.get(
            "/cql",
            params={
                "filter": json.dumps(
                    {"op": "=", "args": [{"property": "not-an-iri"}, "Gold"]}
                )
            },
        )

    assert response.status_code == 400
    assert "CQL property values must be IRIs" in response.json()["detail"]


def test_lucene_cql_post_rejects_non_string_q(test_repo: Repo):
    with _build_lucene_test_client(test_repo) as client:
        response = client.post("/cql", json={"q": 42})

    assert response.status_code == 400
    assert response.json()["detail"] == "POST q must be a string."


def test_lucene_cql_get_rejects_unsupported_facet_before_repo_execution():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.get("/cql", params={"facets": "urn:jena:lucene:field#authorName"})

    assert response.status_code == 400
    assert "Unsupported facet IRIs" in response.json()["detail"]
    assert fake_repo.rdf_queries == []


def test_lucene_cql_post_rejects_invalid_facets_shape_before_repo_execution():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.post("/cql", json={"facets": "urn:jena:lucene:field#state"})

    assert response.status_code == 400
    assert response.json()["detail"] == "POST facets must be an array of IRI strings."
    assert fake_repo.rdf_queries == []


def test_lucene_cql_get_rejects_facets_with_facet_profile():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.get(
            "/cql",
            params={
                "facets": "urn:jena:lucene:field#state",
                "facet_profile": "http://example.com/facet-profile",
            },
        )

    assert response.status_code == 400
    assert "cannot accept both 'facets' and 'facet_profile'" in response.json()["detail"]


def test_lucene_cql_get_rejects_non_iri_property_before_repo_execution():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.get(
            "/cql",
            params={
                "filter": json.dumps(
                    {"op": "=", "args": [{"property": "not-an-iri"}, "Gold"]}
                )
            },
        )

    assert response.status_code == 400
    assert fake_repo.rdf_queries == []
