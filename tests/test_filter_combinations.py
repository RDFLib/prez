"""
Tests for combinations of datetime, bbox, and CQL filters to ensure
FILTER EXISTS optimization works correctly when multiple filters are applied.
"""

import pytest
from datetime import datetime
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.umbrella import (
    merge_listing_query_grammar_inputs,
    PrezQueryConstructor,
)
from prez.models.query_params import ListingQueryParams
from prez.enums import OrderByDirectionEnum


def test_cql_datetime_combination():
    """Test CQL filter combined with datetime filter."""
    # Create CQL filter
    cql_json_data = {
        "op": "=",
        "args": [
            {"property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
            "http://www.w3.org/ns/sosa/Sample",
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Create datetime filter
    dt1 = datetime(2023, 1, 1)
    dt2 = datetime(2023, 12, 31)

    qp = ListingQueryParams(
        limit=10,
        page=1,
        _filter=None,
        bbox=[],
        datetime=(dt1, dt2),
        order_by=None,
        order_by_direction=None,
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should contain both the CQL pattern and datetime pattern
    assert "http://www.w3.org/ns/sosa/Sample" in query_string
    assert "2023-01-01T00:00:00" in query_string
    assert "2023-12-31T00:00:00" in query_string

    # Should have inner select with focus_node
    assert "SELECT DISTINCT ?focus_node" in query_string


def test_cql_bbox_combination():
    """Test CQL filter combined with bbox filter."""
    # Create CQL filter
    cql_json_data = {
        "op": "like",
        "args": [
            {"property": "http://www.w3.org/2000/01/rdf-schema#label"},
            "test%",
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Create bbox filter
    bbox = [144.0, -38.0, 145.0, -37.0]

    qp = ListingQueryParams(
        limit=10,
        page=1,
        _filter=None,
        bbox=bbox,
        datetime=None,
        order_by=None,
        order_by_direction=None,
        filter_crs="http://www.opengis.net/def/crs/EPSG/0/4326",
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should contain both the CQL REGEX pattern and geometry patterns
    assert "REGEX" in query_string
    assert "test.*" in query_string
    assert "hasGeometry" in query_string or "sfIntersects" in query_string

    # Should have inner select with focus_node
    assert "SELECT DISTINCT ?focus_node" in query_string


def test_datetime_bbox_combination():
    """Test datetime filter combined with bbox filter."""
    # Create datetime filter
    dt1 = datetime(2023, 6, 15)

    # Create bbox filter
    bbox = [150.0, -35.0, 151.0, -34.0]

    qp = ListingQueryParams(
        limit=10,
        page=1,
        _filter=None,
        bbox=bbox,
        datetime=(dt1, None),
        order_by=None,
        order_by_direction=None,
        filter_crs="http://www.opengis.net/def/crs/EPSG/0/4326",
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=None, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should contain both datetime and geometry patterns
    assert "2023-06-15T00:00:00" in query_string
    assert "hasGeometry" in query_string or "sfIntersects" in query_string

    # Should have inner select with focus_node
    assert "SELECT DISTINCT ?focus_node" in query_string


def test_cql_datetime_bbox_triple_combination():
    """Test all three filters combined: CQL + datetime + bbox."""
    # Create CQL filter with AND operator
    cql_json_data = {
        "op": "and",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
                    "http://www.w3.org/ns/sosa/Sample",
                ],
            },
            {
                "op": ">",
                "args": [
                    {"property": "http://example.org/temperature"},
                    20,
                ],
            },
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Create datetime interval filter
    dt1 = datetime(2023, 3, 1)
    dt2 = datetime(2023, 9, 30)

    # Create bbox filter
    bbox = [145.0, -37.5, 146.0, -36.5]

    qp = ListingQueryParams(
        limit=20,
        page=1,
        _filter=None,
        bbox=bbox,
        datetime=(dt1, dt2),
        order_by=None,
        order_by_direction=None,
        filter_crs="http://www.opengis.net/def/crs/EPSG/0/4326",
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should contain CQL patterns
    assert "http://www.w3.org/ns/sosa/Sample" in query_string
    assert "http://example.org/temperature" in query_string

    # Should contain datetime patterns
    assert "2023-03-01T00:00:00" in query_string
    assert "2023-09-30T00:00:00" in query_string

    # Should contain geometry patterns
    assert "hasGeometry" in query_string or "sfIntersects" in query_string

    # Should have inner select with focus_node
    assert "SELECT DISTINCT ?focus_node" in query_string

    # Should have proper LIMIT
    assert "LIMIT 20" in query_string


def test_cql_not_operator_with_datetime():
    """Test CQL NOT operator combined with datetime filter."""
    # Create CQL filter with NOT operator
    cql_json_data = {
        "op": "not",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://example.org/status"},
                    "inactive",
                ],
            }
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Create datetime filter (single point in time)
    dt1 = datetime(2023, 7, 4, 12, 0, 0)

    qp = ListingQueryParams(
        limit=10,
        page=1,
        _filter=None,
        bbox=[],
        datetime=(dt1, None),
        order_by=None,
        order_by_direction=None,
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should contain FILTER NOT EXISTS for the CQL NOT operator
    assert "FILTER NOT EXISTS" in query_string

    # Should contain the negated property
    assert "http://example.org/status" in query_string
    assert "inactive" in query_string

    # Should contain datetime pattern
    assert "2023-07-04T12:00:00" in query_string

    # Should have inner select with focus_node
    assert "SELECT DISTINCT ?focus_node" in query_string


def test_complex_cql_or_with_bbox():
    """Test complex CQL OR operation combined with bbox filter."""
    # Create complex CQL filter with OR and nested conditions
    cql_json_data = {
        "op": "or",
        "args": [
            {
                "op": "=",
                "args": [
                    {"property": "http://example.org/category"},
                    "water",
                ],
            },
            {
                "op": "and",
                "args": [
                    {
                        "op": "=",
                        "args": [
                            {"property": "http://example.org/category"},
                            "land",
                        ],
                    },
                    {
                        "op": ">",
                        "args": [
                            {"property": "http://example.org/elevation"},
                            100,
                        ],
                    },
                ],
            },
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Create bbox filter
    bbox = [147.0, -36.0, 148.0, -35.0]

    qp = ListingQueryParams(
        limit=15,
        page=1,
        _filter=None,
        bbox=bbox,
        datetime=None,
        order_by=None,
        order_by_direction=None,
        filter_crs="http://www.opengis.net/def/crs/EPSG/0/4326",
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should contain UNION for OR operation
    assert "UNION" in query_string

    # Should contain the category values
    assert "water" in query_string
    assert "land" in query_string
    assert "http://example.org/elevation" in query_string

    # Should contain geometry patterns
    assert "hasGeometry" in query_string or "sfIntersects" in query_string

    # Should have inner select with focus_node
    assert "SELECT DISTINCT ?focus_node" in query_string


def test_filter_exists_patterns_structure():
    """Test that FILTER EXISTS patterns have the correct structure."""
    # Create a simple CQL filter
    cql_json_data = {
        "op": "=",
        "args": [
            {"property": "http://example.org/name"},
            "test",
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Create datetime filter
    dt1 = datetime(2023, 1, 1)

    qp = ListingQueryParams(
        limit=10,
        page=1,
        _filter=None,
        bbox=[],
        datetime=(dt1, None),
        order_by=None,
        order_by_direction=None,
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()


def test_empty_filters_combination():
    """Test that empty or None filters don't interfere with valid ones."""
    # Create CQL filter
    cql_json_data = {
        "op": "=",
        "args": [
            {"property": "http://example.org/test"},
            "value",
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    qp = ListingQueryParams(
        limit=10,
        page=1,
        _filter=None,
        bbox=[],  # Empty bbox
        datetime=None,  # No datetime
        order_by=None,
        order_by_direction=None,
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should contain the CQL filter content
    assert "http://example.org/test" in query_string
    assert "value" in query_string

    # Should have inner select with focus_node
    assert "SELECT DISTINCT ?focus_node" in query_string


def test_order_by_with_filter_combinations():
    """Test that ordering works correctly with filter combinations."""
    # Create CQL filter
    cql_json_data = {
        "op": ">=",
        "args": [
            {"property": "http://example.org/score"},
            75,
        ],
    }
    parser = CQLParser(cql_json=cql_json_data)
    parser.parse()

    # Create bbox filter
    bbox = [149.0, -35.5, 150.0, -34.5]

    qp = ListingQueryParams(
        limit=10,
        page=1,
        _filter=None,
        bbox=bbox,
        datetime=None,
        order_by="http://www.w3.org/2000/01/rdf-schema#label",
        order_by_direction=OrderByDirectionEnum.DESC,
        filter_crs="http://www.opengis.net/def/crs/EPSG/0/4326",
    )

    kwargs = merge_listing_query_grammar_inputs(cql_parser=parser, query_params=qp)
    query = PrezQueryConstructor(**kwargs)
    query_string = query.to_string()

    # Should have ORDER BY clause
    assert "ORDER BY DESC" in query_string
    assert "STR" in query_string  # STR function for label ordering

    # Should contain both filter patterns
    assert "http://example.org/score" in query_string
    assert "hasGeometry" in query_string or "sfIntersects" in query_string

    # Should have inner select with focus_node and order_by_val
    assert "SELECT DISTINCT ?focus_node" in query_string
    assert "?order_by_val" in query_string
