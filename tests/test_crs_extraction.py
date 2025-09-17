from prez.services.query_generation.spatial_filter import (
    extract_crs_code,
    get_wkt_from_coords,
)


def test_extract_crs_code():
    # HTTP URIs
    assert extract_crs_code("http://www.opengis.net/def/crs/EPSG/0/4326") == "4326"
    assert extract_crs_code("http://www.opengis.net/def/crs/OGC/1.3/CRS84") == "CRS84"
    assert extract_crs_code("http://www.opengis.net/def/crs/EPSG/0/3857") == "3857"
    assert extract_crs_code("http://www.opengis.net/def/crs/OGC/2/84") == "84"

    # HTTPS URIs
    assert extract_crs_code("https://www.opengis.net/def/crs/EPSG/9.9.1/4326") == "4326"
    assert extract_crs_code("https://www.opengis.net/def/crs/OGC/1.3/CRS84") == "CRS84"
    assert extract_crs_code("https://www.opengis.net/def/crs/EPSG/0/3857") == "3857"

    # URNs
    assert extract_crs_code("urn:ogc:def:crs:EPSG::4326") == "4326"
    assert extract_crs_code("urn:ogc:def:crs:EPSG:9.9.1:4326") == "4326"
    assert extract_crs_code("urn:ogc:def:crs:OGC:1.3:CRS84") == "CRS84"
    assert extract_crs_code("urn:ogc:def:crs:EPSG::3857") == "3857"
    assert extract_crs_code("urn:ogc:def:crs:OGC:2:84") == "84"

    # Edge cases
    assert extract_crs_code("") is None
    assert extract_crs_code(None) is None
    assert extract_crs_code("http://www.opengis.net/def/crs/EPSG/0/4326/") == "4326"


def test_get_wkt_from_coords():
    # Test EPSG:4326 - should always return full URL
    srid, wkt = get_wkt_from_coords(
        [1.0, 2.0], "Point", "http://www.opengis.net/def/crs/EPSG/0/4326"
    )
    assert srid == "http://www.opengis.net/def/crs/EPSG/0/4326"
    assert "POINT" in wkt

    # Test EPSG:3857 - should always return full URL
    srid, wkt = get_wkt_from_coords([1.0, 2.0], "Point", "urn:ogc:def:crs:EPSG::3857")
    assert srid == "urn:ogc:def:crs:EPSG::3857"
    assert "POINT" in wkt

    # Test CRS84 - should always return full URL
    srid, wkt = get_wkt_from_coords(
        [1.0, 2.0], "Point", "https://www.opengis.net/def/crs/OGC/1.3/CRS84"
    )
    assert srid == "https://www.opengis.net/def/crs/OGC/1.3/CRS84"
    assert "POINT" in wkt

    # Test OGC 84 - should always return full URL
    srid, wkt = get_wkt_from_coords([1.0, 2.0], "Point", "urn:ogc:def:crs:OGC:2:84")
    assert srid == "urn:ogc:def:crs:OGC:2:84"
    assert "POINT" in wkt
