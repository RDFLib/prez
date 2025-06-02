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
