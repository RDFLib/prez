import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pyoxigraph import Store, DefaultGraph, NamedNode, Literal, Quad
from rdflib import Graph, RDF, Literal as RDFlibLiteral, URIRef
from sparql_grammar_pydantic import ConstructQuery, IRI, TriplesSameSubject, Var

from prez.app import assemble_app
from prez.config import Settings, settings as global_settings
from prez.dependencies import (
    cql_get_parser_dependency,
    cql_post_listing_parser_dependency,
    generate_concept_hierarchy_query,
    generate_search_query,
    generate_search_query_post,
    get_data_repo,
    get_endpoint_nodeshapes,
    get_endpoint_structure,
    get_endpoint_structure_listing_post,
    get_negotiated_pmts,
    get_negotiated_pmts_listing_post,
    get_profile_nodeshape,
    get_profile_nodeshape_listing_post,
    get_queryable_props,
    get_system_repo,
    get_url,
)
from prez.models.query_params import ListingQueryParams
from prez.repositories import Repo
from prez.reference_data.prez_ns import EP, ONT, PREZ
from prez.routers.cql_lucene_router import router as cql_lucene_router
from prez.services.listings import listing_function
from prez.services.query_generation.search_jena_lucene import SearchQueryJenaLucene


class FakeLuceneListingRepo(Repo):
    def __init__(self, profile_query_matchers: list[tuple[str, Quad]] | None = None):
        self.rdf_queries: list[list[str]] = []
        self.tabular_queries: list[list] = []
        self.return_oxigraph_store_flags: list[bool] = []
        self.profile_query_matchers = profile_query_matchers or []

    def _build_result_store(self) -> Store:
        store = Store()
        default = DefaultGraph()
        focus_node = NamedNode("http://example.com/resource/1")
        hash_node = NamedNode("urn:hash:1")
        match_node = NamedNode("urn:match:1")
        store.add(Quad(focus_node, NamedNode(str(PREZ.type)), NamedNode(str(PREZ.FocusNode)), default))
        store.add(Quad(focus_node, NamedNode(str(RDF.type)), NamedNode("http://example.com/Class"), default))
        store.add(Quad(hash_node, NamedNode(str(RDF.type)), NamedNode(str(PREZ.SearchResult)), default))
        store.add(Quad(hash_node, NamedNode(str(PREZ.searchResultURI)), focus_node, default))
        store.add(Quad(hash_node, NamedNode(str(PREZ.hasSearchMatch)), match_node, default))
        store.add(Quad(match_node, NamedNode(str(RDF.type)), NamedNode(str(PREZ.SearchResultMatch)), default))
        store.add(Quad(match_node, NamedNode(str(PREZ.searchResultMatch)), Literal("deep"), default))
        store.add(
            Quad(
                match_node,
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
            main_query = rdf_queries[0] if rdf_queries else ""
            for query_fragment, quad in self.profile_query_matchers:
                if query_fragment in main_query:
                    store.add(quad)
            if any("urn:jena:lucene:index#facet" in query for query in rdf_queries):
                facet_node = NamedNode("urn:facet:1")
                store.add(Quad(facet_node, NamedNode(str(PREZ.facetName)), NamedNode("urn:jena:lucene:field#commodity"), default))
                store.add(Quad(facet_node, NamedNode(str(PREZ.facetValue)), Literal("Gold"), default))
                store.add(Quad(facet_node, NamedNode(str(PREZ.facetCount)), Literal("2"), default))
            return store, []
        if tabular_queries:
            return Graph(), [(None, []) for _ in tabular_queries]
        return Graph(), []

    async def rdf_query_to_rdflib_graph(self, query: str, into_graph: Graph | None = None):
        graph = into_graph if into_graph is not None else Graph()
        commodity = URIRef("urn:jena:lucene:field#commodity")
        state = URIRef("urn:jena:lucene:field#state")
        graph.add((commodity, URIRef(str(ONT.facetable)), RDFlibLiteral(True)))
        graph.add((state, URIRef(str(ONT.facetable)), RDFlibLiteral(True)))
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
    default_profile_uri: str = "http://example.org/profile",
    profile_tss_list: list[TriplesSameSubject] | None = None,
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
    def _build_fake_profile_nodeshape(profile_uri: str):
        return SimpleNamespace(
            uri=profile_uri,
            focus_node=Var(value="focus_node"),
            tss_list=list(profile_tss_list or []),
            tssp_list=[],
            gpnt_list=[],
        )

    class FakePMTs:
        def __init__(self, mediatype: str, profile_uri: str):
            self.selected = {
                "mediatype": mediatype,
                "profile": profile_uri,
                "class": URIRef("http://example.com/Class"),
            }
            self.requested_mediatypes = (
                [(mediatype, 1.0)] if mediatype == "application/sparql-query" else None
            )

        def generate_response_headers(self):
            return {}

    async def _get_fake_pmts(request: Request):
        mediatype = request.query_params.get("_mediatype", "text/turtle")
        profile_uri = request.query_params.get("_profile", default_profile_uri)
        return FakePMTs(mediatype, profile_uri)

    async def _get_fake_pmts_post(request: Request):
        body = await request.json()
        mediatype = body.get("_mediatype", "text/turtle") if isinstance(body, dict) else "text/turtle"
        profile_uri = (
            body.get("_profile", default_profile_uri)
            if isinstance(body, dict)
            else default_profile_uri
        )
        return FakePMTs(mediatype, profile_uri)

    async def _get_fake_profile_nodeshape(request: Request):
        return _build_fake_profile_nodeshape(
            request.query_params.get("_profile", default_profile_uri)
        )

    async def _get_fake_profile_nodeshape_post(request: Request):
        body = await request.json()
        profile_uri = (
            body.get("_profile", default_profile_uri)
            if isinstance(body, dict)
            else default_profile_uri
        )
        return _build_fake_profile_nodeshape(profile_uri)

    app.dependency_overrides[get_data_repo] = lambda: test_repo
    app.dependency_overrides[get_system_repo] = lambda: test_repo
    app.dependency_overrides[get_endpoint_nodeshapes] = lambda: fake_endpoint_nodeshape
    app.dependency_overrides[get_profile_nodeshape] = _get_fake_profile_nodeshape
    app.dependency_overrides[get_profile_nodeshape_listing_post] = (
        _get_fake_profile_nodeshape_post
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


def _make_request(url: str, *, method: str = "GET", json_body: dict | None = None) -> Request:
    body_bytes = (
        b""
        if json_body is None
        else json.dumps(json_body).encode("utf-8")
    )

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": url.split("?", 1)[0],
        "raw_path": url.split("?", 1)[0].encode("utf-8"),
        "query_string": url.split("?", 1)[1].encode("utf-8") if "?" in url else b"",
        "headers": (
            [(b"content-type", b"application/json")]
            if json_body is not None
            else []
        ),
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    return Request(scope, receive)


class _FakePMTs:
    def __init__(self, mediatype: str = "text/turtle", profile_uri: str = "http://example.org/profile"):
        self.selected = {
            "mediatype": mediatype,
            "profile": profile_uri,
            "class": URIRef("http://example.com/Class"),
        }
        self.requested_mediatypes = None

    def generate_response_headers(self):
        return {}



def test_lucene_feature_flag_requires_dataset_name():
    settings = Settings(
        enable_cql_jena_lucene_json=True,
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )

    assert settings.enable_cql_jena_lucene_json is True


def test_lucene_feature_flag_requires_remote_repo():
    with pytest.raises(ValueError, match="sparql_repo_type=remote"):
        Settings(
            enable_cql_jena_lucene_json=True,
            sparql_repo_type="pyoxigraph_memory",
            jena_fuseki_dataset_name="dataset",
        )


def test_jena_assembler_path_requires_dataset_name():
    settings = Settings(jena_assembler_path="/tmp/config.ttl")

    assert settings.jena_assembler_path == "/tmp/config.ttl"


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
    assert "(?hit ?focus_node ?weight ?totalHits)" in query_fragment
    assert '("default" "default" "*" "" "" 106)' in query_fragment
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

    assert "(?hit ?focus_node ?weight ?totalHits)" in query_fragment
    assert '("custom-index" "default" "ore"' in query_fragment
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"http://example.com/predicate\\"},\\"Gold\\"]}"'
        in query_fragment
    )
    assert query_fragment.endswith("16) .")


def test_search_query_jena_lucene_builds_combined_construct_query_for_facets():
    search_query = SearchQueryJenaLucene(
        term="deep",
        limit=10,
        offset=0,
        facets=[
            "urn:jena:lucene:field#commodity",
            "urn:jena:lucene:field#state",
        ],
        filter_json={
            "op": "=",
            "args": [{"property": "urn:jena:lucene:field#commodity"}, "Gold"],
        },
        lucene_index_name="default",
    )

    combined_query = search_query.build_combined_query(
        construct_tss_list=search_query.tss_list + search_query.facet_tss_list,
        profile_triples=[],
        profile_gpnt=[],
    )
    query_string = search_query.normalize_query_string(combined_query.to_string())

    assert isinstance(combined_query, ConstructQuery)
    assert "UNION" in query_string
    assert "urn:jena:lucene:index#query" in query_string
    assert "urn:jena:lucene:index#match" in query_string
    assert "urn:jena:lucene:index#facet" in query_string
    assert "<https://prez.dev/hasSearchMatch> ?searchMatch" in query_string
    assert "<https://prez.dev/facetName> ?facetName" in query_string
    assert (
        '"[\\"urn:jena:lucene:field#commodity\\",\\"urn:jena:lucene:field#state\\"]"'
        in query_string
    )
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"'
        in query_string
    )
    assert '("default" "default" "deep"' in query_string


def test_lucene_cql_get_supports_conneg_and_uses_default_limit(test_repo: Repo):
    with _build_lucene_test_client(test_repo) as client:
        response = client.get("/cql", params={"_mediatype": "application/sparql-query"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/sparql-query")
    assert "CONSTRUCT" in response.text
    assert "urn:jena:lucene:index#query" in response.text
    assert "urn:jena:lucene:index#match" in response.text
    assert "(?hit ?focus_node ?weight ?totalHits)" in response.text
    assert "<https://prez.dev/count> ?totalHits" in response.text
    assert '("default" "default" "*" "" "" 78)' in response.text
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
    assert "urn:jena:lucene:index#match" in response.text
    assert "(?hit ?focus_node ?weight ?totalHits)" in response.text
    assert "<https://prez.dev/count> ?totalHits" in response.text
    assert '("custom-index" "default" "ore"' in response.text
    assert (
        '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"'
        in response.text
    )


@pytest.mark.asyncio
async def test_generate_search_query_uses_lucene_when_feature_flag_enabled(test_repo: Repo):
    runtime_settings = Settings(
        enable_cql_jena_lucene_json=True,
        lucene_default_limit=77,
        lucene_index_name="shacl",
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )
    query_params = ListingQueryParams(
        page=1,
        q="ore",
        _filter=json.dumps(
            {
                "op": "=",
                "args": [
                    {"property": "urn:jena:lucene:field#commodity"},
                    "Gold",
                ],
            }
        ),
        limit=5,
        offset=10,
    )

    search_query = await generate_search_query(
        request=_make_request(
            "/search?q=ore&limit=5&offset=10&filter=%7B%7D"
        ),
        query_params=query_params,
        system_repo=test_repo,
        endpoint_uri_type=(EP["extended-ogc-records/search"], ONT["ListingEndpoint"]),
        runtime_settings=runtime_settings,
    )

    assert isinstance(search_query, SearchQueryJenaLucene)
    assert "(?hit ?focus_node ?weight ?totalHits)" in search_query.valid_lucene_query_triple
    assert '("shacl" "default" "ore"' in search_query.valid_lucene_query_triple


@pytest.mark.asyncio
async def test_generate_search_query_with_filter_only_uses_wildcard_lucene_query(
    test_repo: Repo,
):
    runtime_settings = Settings(
        enable_cql_jena_lucene_json=True,
        lucene_default_limit=77,
        lucene_index_name="default",
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )
    query_params = ListingQueryParams(
        page=1,
        limit=10,
        q=None,
        _filter=json.dumps(
            {
                "op": "=",
                "args": [
                    {"property": "urn:jena:lucene:field#commodity"},
                    "Gold",
                ],
            }
        )
    )

    search_query = await generate_search_query(
        request=_make_request("/search?filter=%7B%7D"),
        query_params=query_params,
        system_repo=test_repo,
        endpoint_uri_type=(EP["extended-ogc-records/search"], ONT["ListingEndpoint"]),
        runtime_settings=runtime_settings,
    )

    assert isinstance(search_query, SearchQueryJenaLucene)
    assert '("default" "default" "*"' in search_query.valid_lucene_query_triple
    assert '"{\\"op\\":\\"=\\",\\"args\\":[{\\"property\\":\\"urn:jena:lucene:field#commodity\\"},\\"Gold\\"]}"' in search_query.valid_lucene_query_triple
    assert search_query.valid_lucene_query_triple.endswith('78) .')
    assert search_query.limit == 78


@pytest.mark.asyncio
async def test_search_parser_dependencies_stand_down_for_lucene_search():
    runtime_settings = Settings(
        enable_cql_jena_lucene_json=True,
        lucene_default_limit=77,
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )
    query_params = ListingQueryParams(
        page=1,
        limit=10,
        _filter=json.dumps(
            {
                "op": "=",
                "args": [
                    {"property": "urn:jena:lucene:field#commodity"},
                    "Gold",
                ],
            }
        )
    )

    get_parser = await cql_get_parser_dependency(
        query_params=query_params,
        queryable_props=[],
        endpoint_uri_type=(EP["extended-ogc-records/search"], ONT["ListingEndpoint"]),
        runtime_settings=runtime_settings,
    )
    post_parser = await cql_post_listing_parser_dependency(
        query_params=query_params,
        queryable_props=[],
        endpoint_uri_type=(EP["extended-ogc-records/search-post"], ONT["ListingEndpoint"]),
        runtime_settings=runtime_settings,
    )

    assert get_parser is None
    assert post_parser is None


@pytest.mark.asyncio
async def test_generate_search_query_post_uses_lucene_when_feature_flag_enabled(
    test_repo: Repo,
):
    runtime_settings = Settings(
        enable_cql_jena_lucene_json=True,
        lucene_default_limit=77,
        lucene_index_name="default",
        sparql_repo_type="remote",
        sparql_endpoint="http://example.com/dataset/sparql",
    )
    body = {
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
    }
    query_params = ListingQueryParams(
        page=1,
        q="ore",
        _filter=json.dumps(body["filter"]),
        limit=5,
        offset=10,
    )

    search_query = await generate_search_query_post(
        request=_make_request("/search", method="POST", json_body=body),
        query_params=query_params,
        system_repo=test_repo,
        endpoint_uri_type=(EP["extended-ogc-records/search-post"], ONT["ListingEndpoint"]),
        runtime_settings=runtime_settings,
    )

    assert isinstance(search_query, SearchQueryJenaLucene)
    assert '("default" "default" "ore"' in search_query.valid_lucene_query_triple
    assert search_query.valid_lucene_query_triple.endswith("16) .")


@pytest.mark.asyncio
async def test_listing_function_lucene_uses_single_query_and_preserves_total_hits(
    monkeypatch,
):
    fake_repo = FakeLuceneListingRepo()
    search_query = SearchQueryJenaLucene(
        term="deep",
        filter_json={
            "op": "=",
            "args": [
                {"property": "urn:jena:lucene:field#commodity"},
                "Gold",
            ],
        },
        limit=5,
        offset=0,
        lucene_index_name="default",
    )
    endpoint_nodeshape = SimpleNamespace(
        uri="http://example.org/ns#Search",
        tssp_list=[],
        gpnt_list=[],
        tssp_exists_list=[],
        gpnt_exists_list=[],
    )
    profile_nodeshape = SimpleNamespace(
        focus_node=Var(value="focus_node"),
        tss_list=[],
        tssp_list=[],
        gpnt_list=[],
    )
    captured = {}

    async def _fake_return_from_graph(
        item_store,
        selected_mediatype,
        selected_profile,
        response_headers,
        selected_class,
        data_repo,
        system_repo,
        query_params,
        url,
    ):
        captured["store"] = item_store
        return item_store

    monkeypatch.setattr("prez.services.listings.return_from_graph", _fake_return_from_graph)

    result = await listing_function(
        data_repo=fake_repo,
        system_repo=fake_repo,
        endpoint_nodeshape=endpoint_nodeshape,
        endpoint_structure=tuple(),
        search_query=search_query,
        concept_hierarchy_query=None,
        cql_parser=None,
        pmts=_FakePMTs(),
        profile_nodeshape=profile_nodeshape,
        query_params=ListingQueryParams(
            page=1,
            limit=5,
            q=None,
            _filter=None,
            bbox=[],
            datetime=None,
            filter_crs="http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            order_by=None,
            order_by_direction=None,
            facet_profile=None,
            mediatype="text/turtle",
            profile=None,
            subscription_key=None,
            startindex=None,
            offset=None,
        ),
        original_endpoint_type=ONT["ListingEndpoint"],
        url="http://testserver/search",
    )

    assert result is captured["store"]
    assert len(fake_repo.rdf_queries) == 1
    assert len(fake_repo.rdf_queries[0]) == 1
    assert "urn:jena:lucene:index#query" in fake_repo.rdf_queries[0][0]
    assert "COUNT(" not in fake_repo.rdf_queries[0][0]

    count_quads = list(
        captured["store"].quads_for_pattern(
            NamedNode(str(PREZ.SearchResult)),
            NamedNode(str(PREZ["count"])),
            None,
            None,
        )
    )
    assert len(count_quads) == 1
    assert count_quads[0].object.value == "2"


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
    assert "urn:jena:lucene:index#match" in response.text
    assert "(?hit ?focus_node ?weight ?totalHits)" in response.text
    assert "<https://prez.dev/count> ?totalHits" in response.text
    assert '("default" "default" "ore"' in response.text
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
    assert len(fake_repo.rdf_queries) == 1
    assert len(fake_repo.rdf_queries[0]) == 1
    assert "urn:jena:lucene:index#query" in fake_repo.rdf_queries[0][0]
    assert "urn:jena:lucene:index#match" in fake_repo.rdf_queries[0][0]
    assert "(?hit ?focus_node ?weight ?totalHits)" in fake_repo.rdf_queries[0][0]
    assert '("default" "default" "deep"' in fake_repo.rdf_queries[0][0]
    assert "COUNT(" not in fake_repo.rdf_queries[0][0]
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
        URIRef("urn:hash:1"),
        URIRef(str(PREZ.hasSearchMatch)),
        URIRef("urn:match:1"),
    ) in rendered_graph
    assert (
        URIRef("urn:match:1"),
        URIRef(str(PREZ.searchResultMatch)),
        None,
    ) in rendered_graph
    assert (
        URIRef(str(PREZ.SearchResult)),
        URIRef(str(PREZ["count"])),
        RDFlibLiteral("2"),
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
    assert len(fake_repo.rdf_queries) == 1
    assert len(fake_repo.rdf_queries[0]) == 1
    assert "urn:jena:lucene:index#query" in fake_repo.rdf_queries[0][0]
    assert "urn:jena:lucene:index#match" in fake_repo.rdf_queries[0][0]
    assert "(?hit ?focus_node ?weight ?totalHits)" in fake_repo.rdf_queries[0][0]
    assert '("default" "default" "deep"' in fake_repo.rdf_queries[0][0]
    assert "COUNT(" not in fake_repo.rdf_queries[0][0]
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
        URIRef("urn:hash:1"),
        URIRef(str(PREZ.hasSearchMatch)),
        URIRef("urn:match:1"),
    ) in rendered_graph
    assert (
        URIRef(str(PREZ.SearchResult)),
        URIRef(str(PREZ["count"])),
        RDFlibLiteral("2"),
    ) in rendered_graph


def test_lucene_cql_get_rendered_path_uses_wildcard_and_default_limit():
    fake_repo = FakeLuceneListingRepo()
    with _build_lucene_test_client(fake_repo) as client:
        response = client.get("/cql", params={"_mediatype": "text/turtle"})

    assert response.status_code == 200
    assert fake_repo.return_oxigraph_store_flags == [True]
    assert '("default" "default" "*" "" "" 78)' in fake_repo.rdf_queries[0][0]


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
    assert "# Query 2" not in response.text
    assert "UNION" in response.text
    assert "urn:jena:lucene:index#query" in response.text
    assert "urn:jena:lucene:index#facet" in response.text


def test_lucene_cql_get_accepts_facets_in_one_lucene_query():
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
    assert len(fake_repo.rdf_queries[0]) == 1
    assert "urn:jena:lucene:index#query" in fake_repo.rdf_queries[0][0]
    assert "urn:jena:lucene:index#facet" in fake_repo.rdf_queries[0][0]
    assert "UNION" in fake_repo.rdf_queries[0][0]
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert (
        None,
        URIRef(str(PREZ.facetName)),
        URIRef("urn:jena:lucene:field#commodity"),
    ) in rendered_graph


def test_lucene_cql_post_accepts_facets_in_one_lucene_query():
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
    assert len(fake_repo.rdf_queries[0]) == 1
    assert "urn:jena:lucene:index#query" in fake_repo.rdf_queries[0][0]
    assert "urn:jena:lucene:index#facet" in fake_repo.rdf_queries[0][0]
    assert "UNION" in fake_repo.rdf_queries[0][0]


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


def test_lucene_cql_get_annotated_response_includes_requested_profile_expansion_and_annotations():
    profile_predicate = URIRef("http://example.com/profilePredicate")
    annotation_predicate = URIRef("http://example.com/annotationPredicate")
    requested_profile = "http://example.com/profile/custom"
    profile_object = URIRef("http://example.com/profile-expanded-object")
    annotation_value = "annotation value"
    profile_quad = Quad(
        NamedNode("http://example.com/resource/1"),
        NamedNode(str(profile_predicate)),
        NamedNode(str(profile_object)),
        DefaultGraph(),
    )
    fake_repo = FakeLuceneListingRepo(
        profile_query_matchers=[(str(profile_predicate), profile_quad)]
    )
    profile_tss_list = [
        TriplesSameSubject.from_spo(
            subject=Var(value="focus_node"),
            predicate=IRI(value=str(profile_predicate)),
            object=IRI(value=str(profile_object)),
        )
    ]

    async def _fake_annotations(store, repo, system_repo):
        annotations = Store()
        annotations.add(
            Quad(
                NamedNode("http://example.com/resource/1"),
                NamedNode(str(annotation_predicate)),
                Literal(annotation_value),
                DefaultGraph(),
            )
        )
        return annotations

    with patch(
        "prez.renderers.renderer.return_annotated_rdf_for_oxigraph",
        side_effect=_fake_annotations,
    ):
        with _build_lucene_test_client(
            fake_repo,
            default_profile_uri="http://example.com/profile/default",
            profile_tss_list=profile_tss_list,
        ) as client:
            response = client.get(
                "/cql",
                params={
                    "_mediatype": "text/anot+turtle",
                    "_profile": requested_profile,
                },
            )

    assert response.status_code == 200
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert (
        None,
        PREZ.currentProfile,
        URIRef(requested_profile),
    ) in rendered_graph
    assert (
        URIRef("http://example.com/resource/1"),
        profile_predicate,
        profile_object,
    ) in rendered_graph
    assert (
        URIRef("http://example.com/resource/1"),
        annotation_predicate,
        RDFlibLiteral(annotation_value),
    ) in rendered_graph


def test_lucene_cql_post_annotated_response_includes_requested_profile():
    requested_profile = "http://example.com/profile/post-custom"
    fake_repo = FakeLuceneListingRepo()

    with _build_lucene_test_client(fake_repo) as client:
        response = client.post(
            "/cql",
            json={
                "_mediatype": "text/anot+turtle",
                "_profile": requested_profile,
                "q": "deep",
            },
        )

    assert response.status_code == 200
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert (
        None,
        PREZ.currentProfile,
        URIRef(requested_profile),
    ) in rendered_graph


def test_lucene_cql_get_annotated_response_includes_generated_links():
    generated_link = "/catalogs/demo/resource/1"
    fake_repo = FakeLuceneListingRepo()

    async def _fake_add_links(store, repo, endpoint_structure, uris=None):
        store.add(
            Quad(
                NamedNode("http://example.com/resource/1"),
                NamedNode(str(PREZ.link)),
                Literal(generated_link),
                DefaultGraph(),
            )
        )

    async def _empty_annotations(store, repo, system_repo):
        return Store()

    with patch(
        "prez.services.listings.add_prez_links_for_oxigraph",
        side_effect=_fake_add_links,
    ), patch(
        "prez.renderers.renderer.return_annotated_rdf_for_oxigraph",
        side_effect=_empty_annotations,
    ):
        with _build_lucene_test_client(fake_repo) as client:
            response = client.get(
                "/cql",
                params={"_mediatype": "text/anot+turtle"},
            )

    assert response.status_code == 200
    rendered_graph = Graph().parse(data=response.text, format="turtle")
    assert (
        URIRef("http://example.com/resource/1"),
        PREZ.link,
        RDFlibLiteral(generated_link),
    ) in rendered_graph
