import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount


@pytest.fixture(scope="function")
def fresh_client(test_repo):
    """
    Function-scoped client that creates a fresh app instance.

    This is needed for tests that run after test_issue_236 which pollutes
    global caches with custom endpoints.
    """
    from prez.app import assemble_app
    from prez.dependencies import get_data_repo

    def override_get_repo():
        return test_repo

    app = assemble_app()
    app.dependency_overrides[get_data_repo] = override_get_repo

    for route in app.routes:
        if isinstance(route, Mount):
            route.app.dependency_overrides[get_data_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def mock_queryables():
    """Fixture to add mock queryables data to the system store for testing"""
    from pyoxigraph import RdfFormat
    from prez.cache import system_store

    queryables_ttl = """
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
        @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix sh: <http://www.w3.org/ns/shacl#> .

        <https://prez/queryables/TestRDFType> a cql:Queryable, sh:PropertyShape ;
            dcterms:identifier "test-type" ;
            sh:description "Filter by RDF type (test data)" ;
            sh:name "Test RDF Type" ;
            sh:path rdf:type .
    """

    # Add the mock queryables to the system store
    system_store.load(queryables_ttl.encode("utf-8"), RdfFormat.TURTLE)
    return queryables_ttl


def test_ogc_features_root(client):
    r = client.get("/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features")
    assert r.status_code == 200


def test_ogc_features_queryables(client):
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/queryables"
    )
    assert r.status_code == 200


def test_ogc_features_queryables_turtle(client, mock_queryables):
    """Test queryables endpoint returns RDF Turtle format"""
    from rdflib import Graph

    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/queryables?_mediatype=text/turtle"
    )
    assert r.status_code == 200
    assert "text/turtle" in r.headers.get("content-type", "")

    # Verify it's valid RDF that can be parsed
    response_graph = Graph().parse(data=r.text, format="turtle")
    assert len(response_graph) > 0

    # Check for queryable type triples
    from rdflib import URIRef, RDF

    queryable_type = URIRef("http://www.opengis.net/doc/IS/cql2/1.0/Queryable")
    queryables = list(response_graph.subjects(RDF.type, queryable_type))
    assert len(queryables) > 0


def test_ogc_features_queryables_annotated_turtle(client, mock_queryables):
    """Test queryables endpoint returns annotated RDF Turtle format"""
    from rdflib import Graph

    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/queryables?_mediatype=text/anot%2Bturtle"
    )
    assert r.status_code == 200
    assert "text/anot+turtle" in r.headers.get("content-type", "")

    # Verify it's valid RDF that can be parsed
    response_graph = Graph().parse(data=r.text, format="turtle")
    assert len(response_graph) > 0

    # Check for queryable type triples
    from rdflib import URIRef, RDF

    queryable_type = URIRef("http://www.opengis.net/doc/IS/cql2/1.0/Queryable")
    queryables = list(response_graph.subjects(RDF.type, queryable_type))
    assert len(queryables) > 0


def test_ogc_features_queryables_rdf_xml(client, mock_queryables):
    """Test queryables endpoint returns RDF/XML format"""
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/queryables?_mediatype=application/rdf%2Bxml"
    )
    assert r.status_code == 200
    assert "application/rdf+xml" in r.headers.get("content-type", "")

    # Verify it's valid RDF that can be parsed
    from rdflib import Graph

    response_graph = Graph().parse(data=r.text, format="xml")
    assert len(response_graph) > 0


def test_ogc_features_queryables_global_turtle(client, mock_queryables):
    """Test global queryables endpoint returns RDF Turtle format"""
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/queryables?_mediatype=text/turtle"
    )
    assert r.status_code == 200
    assert "text/turtle" in r.headers.get("content-type", "")

    # Verify it's valid RDF that can be parsed
    from rdflib import Graph

    response_graph = Graph().parse(data=r.text, format="turtle")
    assert len(response_graph) > 0


def test_bbox_200(client):
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?bbox=4.0,4.0,6.0,6.0&_mediatype=application/sparql-query"
    )
    assert r.status_code == 200


def test_datetime_200(client):
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?datetime=2021-01-01T00:00:00Z/2021-01-02T00:00:00Z&_mediatype=application/sparql-query"
    )
    assert r.status_code == 200


def test_bbox_graphdb_200(client):
    from prez.config import settings

    original_format = settings.spatial_query_format
    settings.spatial_query_format = "graphdb"
    try:
        r = client.get(
            "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections?bbox=4.0,4.0,6.0,6.0&_mediatype=application/sparql-query"
        )
        assert r.status_code == 200
    finally:
        settings.spatial_query_format = original_format


def test_bbox_qlever_200(client):
    from prez.config import settings

    original_format = settings.spatial_query_format
    settings.spatial_query_format = "qlever"
    try:
        r = client.get(
            "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?bbox=4.0,4.0,6.0,6.0&_mediatype=application/sparql-query"
        )
        assert r.status_code == 200
    finally:
        settings.spatial_query_format = original_format


def test_bbox_graphdb_200_crs(client):
    # CRS84 has lon/lat ordering, should NOT be reversed
    from prez.config import settings

    original_format = settings.spatial_query_format
    settings.spatial_query_format = "graphdb"
    try:
        r = client.get(
            "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections?bbox=4.0,4.0,6.0,6.0&_mediatype=application/sparql-query&filter_crs=http://www.opengis.net/def/crs/OGC/1.3/CRS84"
        )
        assert r.status_code == 200
    finally:
        settings.spatial_query_format = original_format


def test_bbox_graphdb_200_4326_crs(client):
    # 4326 has lat/lon ordering; should be reversed.
    from prez.config import settings

    original_format = settings.spatial_query_format
    settings.spatial_query_format = "graphdb"
    try:
        r = client.get(
            "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections?bbox=4.0,4.0,6.0,6.0&_mediatype=application/sparql-query&filter_crs=http://www.opengis.net/def/crs/EPSG/0/4326"
        )
        assert r.status_code == 200
    finally:
        settings.spatial_query_format = original_format


def test_ogc_features_listing_annotated(fresh_client):
    # General regression test that would have caught the bug fixed in #413
    # Uses fresh_client to avoid cache pollution from test_issue_236
    r = fresh_client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections?_profile=mem&_mediatype=text/anot%2Bturtle"
    )
    assert r.status_code == 200
    assert len(r.content) > 0


def test_ogc_features_object_annotated(fresh_client):
    # General regression test
    # Uses fresh_client to avoid cache pollution from test_issue_236
    r = fresh_client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection?_mediatype=text/anot%2Bturtle&_profile=ogcfeat-minimal"
    )
    assert r.status_code == 200
    assert len(r.content) > 0
