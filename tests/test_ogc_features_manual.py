def test_ogc_features_root(client):
    r = client.get("/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features")
    assert r.status_code == 200


def test_ogc_features_queryables(client):
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/queryables"
    )
    assert r.status_code == 200


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


def test_ogc_features_listing_annotated(client):
    # General regression test that would have caught the bug fixed in #413
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections?_profile=mem&_mediatype=text/anot%2Bturtle"
    )
    assert r.status_code == 200
    assert len(r.content) > 0

def test_ogc_features_object_annotated(client):
    # General regression test
    r = client.get(
        "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection?_mediatype=text/anot%2Bturtle&_profile=ogcfeat-minimal"
    )
    assert r.status_code == 200
    assert len(r.content) > 0
