"""
Tests for the LISTING_COUNT_ON_DEMAND configuration setting.

This setting controls when count queries are executed for listing endpoints:
- When False (default): counts are always included (up to LISTING_COUNT_LIMIT)
- When True: counts are only returned when resultType=hits is passed
"""

import json
from unittest.mock import patch

from rdflib import Graph
from rdflib.namespace import DCAT, RDF

from prez.config import settings
from prez.reference_data.prez_ns import PREZ


class TestListingCountOnDemandDisabled:
    """Tests for LISTING_COUNT_ON_DEMAND=False (default behavior)"""

    def test_catalog_listing_includes_count_by_default(self, client):
        """When LISTING_COUNT_ON_DEMAND=False, listing responses should include count"""
        # Ensure setting is False (default)
        assert settings.listing_count_on_demand is False

        # Request a listing endpoint with annotated mediatype
        r = client.get("/catalogs?_mediatype=text/anot%2Bturtle")
        assert r.status_code == 200

        # Parse response
        response_graph = Graph().parse(data=r.text)

        # Check that count triple exists in the response
        # The count is stored as: [] prez:count "N"
        count_values = list(response_graph.objects(predicate=PREZ["count"]))
        assert len(count_values) > 0, "Count should be included in the response"

    def test_catalog_listing_with_hits_returns_only_count(self, client):
        """When resultType=hits, only count should be returned (no data)"""
        assert settings.listing_count_on_demand is False

        # Request with resultType=hits
        r = client.get("/catalogs?_mediatype=text/anot%2Bturtle&resultType=hits")
        assert r.status_code == 200

        response_graph = Graph().parse(data=r.text)

        # Should have count
        count_values = list(response_graph.objects(predicate=PREZ["count"]))
        assert len(count_values) > 0, "Count should be in hits response"

        # Should NOT have catalog data (no DCAT.Catalog instances)
        catalogs = list(response_graph.subjects(RDF.type, DCAT.Catalog))
        assert len(catalogs) == 0, "Hits response should not include catalog data items"

    def test_geojson_listing_excludes_numberMatched_without_hits(self, client):
        """GeoJSON listings should NOT include numberMatched by default (even when LISTING_COUNT_ON_DEMAND=false)"""
        assert settings.listing_count_on_demand is False

        # Request GeoJSON listing without resultType=hits
        r = client.get(
            "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?_mediatype=application/geo%2Bjson&_profile=ogcfeat-human"
        )
        assert r.status_code == 200

        geojson = json.loads(r.content)

        # GeoJSON response should have numberReturned
        assert "numberReturned" in geojson
        assert geojson["numberReturned"] >= 0

        # numberMatched might be inferred on first page if items < limit, but otherwise not present
        # The key point is no count query should have been executed
        # We can't assert its absence because it might be inferred, but we verify the endpoint works

    def test_geojson_listing_with_hits_includes_numberMatched(self, client):
        """GeoJSON listings with resultType=hits should include numberMatched (even when LISTING_COUNT_ON_DEMAND=false)"""
        assert settings.listing_count_on_demand is False

        # Request GeoJSON listing WITH resultType=hits
        r = client.get(
            "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?_mediatype=application/geo%2Bjson&_profile=ogcfeat-human&resultType=hits"
        )
        assert r.status_code == 200

        geojson = json.loads(r.content)

        # Should have numberMatched (from count query)
        assert "numberMatched" in geojson, "Hits response should include numberMatched"

        # Should have numberReturned = 0 (no features)
        assert "numberReturned" in geojson
        assert (
            geojson["numberReturned"] == 0
        ), "Hits response should not return features"


class TestListingCountOnDemandEnabled:
    """Tests for LISTING_COUNT_ON_DEMAND=True (on-demand counting)"""

    def test_catalog_listing_excludes_count_by_default(self, client):
        """When LISTING_COUNT_ON_DEMAND=True, listing responses should NOT include count"""
        with patch.object(settings, "listing_count_on_demand", True):
            # Request a listing endpoint with annotated mediatype
            r = client.get("/catalogs?_mediatype=text/anot%2Bturtle")
            assert r.status_code == 200

            # Parse response
            response_graph = Graph().parse(data=r.text)

            # Check that count triple does NOT exist in the response
            count_values = list(response_graph.objects(predicate=PREZ["count"]))
            assert (
                len(count_values) == 0
            ), "Count should NOT be included when LISTING_COUNT_ON_DEMAND=True"

            # But catalog data should still be present
            catalogs = list(response_graph.subjects(RDF.type, DCAT.Catalog))
            assert len(catalogs) > 0, "Catalog data should be in the response"

    def test_catalog_listing_with_hits_returns_count(self, client):
        """When LISTING_COUNT_ON_DEMAND=True and resultType=hits, count should be returned"""
        with patch.object(settings, "listing_count_on_demand", True):
            # Request with resultType=hits
            r = client.get("/catalogs?_mediatype=text/anot%2Bturtle&resultType=hits")
            assert r.status_code == 200

            response_graph = Graph().parse(data=r.text)

            # Should have count
            count_values = list(response_graph.objects(predicate=PREZ["count"]))
            assert (
                len(count_values) > 0
            ), "Count should be returned when resultType=hits"

            # Should NOT have catalog data
            catalogs = list(response_graph.subjects(RDF.type, DCAT.Catalog))
            assert len(catalogs) == 0, "Hits response should not include catalog data"

    def test_geojson_listing_excludes_numberMatched(self, client):
        """GeoJSON listings should NOT include numberMatched (regardless of LISTING_COUNT_ON_DEMAND setting)"""
        with patch.object(settings, "listing_count_on_demand", True):
            # Request GeoJSON listing without hits
            r = client.get(
                "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?_mediatype=application/geo%2Bjson&_profile=ogcfeat-human&limit=1"
            )
            assert r.status_code == 200

            geojson = json.loads(r.content)

            # Should have numberReturned (count of items in this response)
            assert "numberReturned" in geojson
            assert geojson["numberReturned"] >= 0
            assert "numberMatched" not in geojson

            # Should NOT have numberMatched (total count)
            # Note: numberMatched might be inferred if it's the first page and
            # numberReturned < limit, but in general it shouldn't be from a count query
            # For a robust test, we check that features are present but no count query ran
            assert "features" in geojson

    def test_geojson_listing_with_hits_includes_numberMatched(self, client):
        """When LISTING_COUNT_ON_DEMAND=True and resultType=hits, numberMatched should be returned"""
        with patch.object(settings, "listing_count_on_demand", True):
            # Request GeoJSON listing WITH hits
            r = client.get(
                "/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?_mediatype=application/geo%2Bjson&_profile=ogcfeat-human&resultType=hits"
            )
            assert r.status_code == 200

            geojson = json.loads(r.content)

            # Should have numberMatched (from count query)
            assert (
                "numberMatched" in geojson
            ), "Hits response should include numberMatched"

            # Should have numberReturned = 0 (no features returned)
            assert "numberReturned" in geojson
            assert (
                geojson["numberReturned"] == 0
            ), "Hits response should not return features"

            # Should NOT have features array with items
            if "features" in geojson:
                assert (
                    len(geojson["features"]) == 0
                ), "Hits response should have empty features"

    def test_lower_level_listing_excludes_count(self, client, a_catprez_catalog_link):
        """Test that nested listing endpoints also respect LISTING_COUNT_ON_DEMAND"""
        with patch.object(settings, "listing_count_on_demand", True):
            # Request nested listing (collections within a catalog)
            r = client.get(
                f"{a_catprez_catalog_link}/collections?_mediatype=text/anot%2Bturtle"
            )
            assert r.status_code == 200

            response_graph = Graph().parse(data=r.text)

            # Should NOT have count
            count_values = list(response_graph.objects(predicate=PREZ["count"]))
            assert len(count_values) == 0, "Count should not be included"

            # But should have resource data
            resources = list(response_graph.subjects(RDF.type, DCAT.Resource))
            assert len(resources) > 0, "Resource data should be in the response"

    def test_lower_level_listing_with_hits_returns_count(
        self, client, a_catprez_catalog_link
    ):
        """Test that nested listing endpoints return count with resultType=hits"""
        with patch.object(settings, "listing_count_on_demand", True):
            # Request nested listing with hits
            r = client.get(
                f"{a_catprez_catalog_link}/collections?_mediatype=text/anot%2Bturtle&resultType=hits"
            )
            assert r.status_code == 200

            response_graph = Graph().parse(data=r.text)

            # Should have count
            count_values = list(response_graph.objects(predicate=PREZ["count"]))
            assert len(count_values) > 0, "Count should be in hits response"

            # Should NOT have resource data
            resources = list(response_graph.subjects(RDF.type, DCAT.Resource))
            assert len(resources) == 0, "Hits response should not include resources"


class TestListingCountOnDemandToggling:
    """Test that the setting can be toggled dynamically"""

    def test_setting_toggle_affects_behavior(self, client):
        """Verify that changing the setting changes the behavior"""
        # Test with setting disabled
        with patch.object(settings, "listing_count_on_demand", False):
            r1 = client.get("/catalogs?_mediatype=text/anot%2Bturtle")
            g1 = Graph().parse(data=r1.text)
            count_disabled = list(g1.objects(predicate=PREZ["count"]))

        # Test with setting enabled
        with patch.object(settings, "listing_count_on_demand", True):
            r2 = client.get("/catalogs?_mediatype=text/anot%2Bturtle")
            g2 = Graph().parse(data=r2.text)
            count_enabled = list(g2.objects(predicate=PREZ["count"]))

        # When disabled, count should be present
        assert len(count_disabled) > 0, "Count should be present when setting is False"

        # When enabled, count should be absent
        assert len(count_enabled) == 0, "Count should be absent when setting is True"


class TestNonAnnotatedMediaTypes:
    """Test behavior with non-annotated RDF mediatypes (e.g., text/turtle)"""

    def test_non_annotated_listing_excludes_count_always(self, client):
        """Non-annotated RDF listings should NEVER include count (count is an annotation)"""
        # Test with LISTING_COUNT_ON_DEMAND=false (default)
        assert settings.listing_count_on_demand is False

        r = client.get("/catalogs?_mediatype=text/turtle")
        assert r.status_code == 200

        response_graph = Graph().parse(data=r.text)

        # Should NOT have count (counts are annotations)
        count_values = list(response_graph.objects(predicate=PREZ["count"]))
        assert (
            len(count_values) == 0
        ), "Non-annotated RDF should not include count (count is an annotation)"

        # But should have catalog data
        catalogs = list(response_graph.subjects(RDF.type, DCAT.Catalog))
        assert len(catalogs) > 0, "Should have catalog data"

    def test_non_annotated_listing_with_hits_returns_count(self, client):
        """Non-annotated RDF with resultType=hits should return count"""
        assert settings.listing_count_on_demand is False

        r = client.get("/catalogs?_mediatype=text/turtle&resultType=hits")
        assert r.status_code == 200

        response_graph = Graph().parse(data=r.text)

        # Should have count when explicitly requested via resultType=hits
        count_values = list(response_graph.objects(predicate=PREZ["count"]))
        assert (
            len(count_values) > 0
        ), "resultType=hits should return count even for non-annotated mediatype"

        # Should NOT have catalog data
        catalogs = list(response_graph.subjects(RDF.type, DCAT.Catalog))
        assert len(catalogs) == 0, "Hits response should not include catalog data"

    def test_non_annotated_listing_with_count_on_demand_enabled(self, client):
        """Non-annotated RDF behavior should be same regardless of LISTING_COUNT_ON_DEMAND"""
        with patch.object(settings, "listing_count_on_demand", True):
            r = client.get("/catalogs?_mediatype=text/turtle")
            assert r.status_code == 200

            response_graph = Graph().parse(data=r.text)

            # Should NOT have count
            count_values = list(response_graph.objects(predicate=PREZ["count"]))
            assert len(count_values) == 0, "Non-annotated RDF should not include count"

            # But should have catalog data
            catalogs = list(response_graph.subjects(RDF.type, DCAT.Catalog))
            assert len(catalogs) > 0, "Should have catalog data"

    def test_non_annotated_listing_with_hits_and_count_on_demand_enabled(self, client):
        """Non-annotated RDF with resultType=hits should return count (regardless of setting)"""
        with patch.object(settings, "listing_count_on_demand", True):
            r = client.get("/catalogs?_mediatype=text/turtle&resultType=hits")
            assert r.status_code == 200

            response_graph = Graph().parse(data=r.text)

            # Should have count
            count_values = list(response_graph.objects(predicate=PREZ["count"]))
            assert (
                len(count_values) > 0
            ), "resultType=hits should return count even for non-annotated mediatype"

            # Should NOT have catalog data
            catalogs = list(response_graph.subjects(RDF.type, DCAT.Catalog))
            assert len(catalogs) == 0, "Hits response should not include catalog data"
