"""
Integration tests for issue #236 - link generation with custom endpoints.

These tests verify that links are correctly generated for hierarchical catalogues
when using custom endpoints with hierarchy level 1 (previously links were only
generated for hierarchy level > 1).

The fix changes link_generation.py to generate links for hierarchy level > 0
instead of > 1, and ensures that type triples are properly filtered to avoid
redundant constraints on focus nodes.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store, RdfFormat
from rdflib import Graph, Namespace
from starlette.routing import Mount

from prez.app import assemble_app
from prez.dependencies import get_data_repo
from prez.repositories import PyoxigraphRepo

SCHEMA = Namespace("https://schema.org/")
PREZ = Namespace("https://prez.dev/")


@pytest.fixture(scope="function")
def issue_236_store() -> Store:
    """Create a store with issue_236 test data."""
    store = Store()
    test_data_file = (
        Path(__file__).parent.parent / "test_data" / "issue_236" / "test_data.ttl"
    )
    store.load(test_data_file.read_bytes(), RdfFormat.TURTLE)
    return store


@pytest.fixture(scope="function")
def issue_236_client(issue_236_store: Store):
    """
    Create a test client with custom endpoints from test_data/issue_236/endpoints.ttl.

    This fixture monkey-patches the glob function in create_endpoints_graph to return
    the issue_236 endpoints file instead of the default_endpoints.ttl file.
    """
    issue_236_endpoints = (
        Path(__file__).parent.parent / "test_data" / "issue_236" / "endpoints.ttl"
    )
    issue_236_prefixes = (
        Path(__file__).parent.parent / "test_data" / "issue_236" / "prefixes.ttl"
    )

    original_glob = Path.glob

    def patched_glob(self, pattern):
        """Patched glob that returns issue_236 endpoints and prefixes."""
        if str(self).endswith("data_endpoints_default") and pattern == "*.ttl":
            return [issue_236_endpoints]
        if str(self).endswith("prefixes") and pattern == "*.ttl":
            return [issue_236_prefixes]
        return original_glob(self, pattern)

    with patch.object(Path, "glob", patched_glob):
        with patch(
            "prez.config.settings.endpoint_structure",
            ["catalogues", "collections", "items"],
        ):

            def override_get_repo():
                return PyoxigraphRepo(issue_236_store)

            app = assemble_app()
            app.dependency_overrides[get_data_repo] = override_get_repo

            for route in app.routes:
                if isinstance(route, Mount):
                    route.app.dependency_overrides[get_data_repo] = override_get_repo

            with TestClient(app) as c:
                yield c

            app.dependency_overrides.clear()


class TestIssue236LinkGeneration:
    """Tests for issue #236 - link generation with hierarchy level 1."""

    def test_catalogues_listing_has_links(self, issue_236_client):
        """
        Test that the /catalogues endpoint returns items with properly generated links.

        Before the fix, catalogues at hierarchy level 1 would not have links generated.
        After the fix, they should have links to their object endpoints.
        """
        response = issue_236_client.get("/catalogues")
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        g = Graph()
        g.parse(data=response.text, format="turtle")
        link_strings = [str(link) for link in list(g.objects(predicate=PREZ.link))]
        members_link_strings = [
            str(link) for link in list(g.objects(predicate=PREZ.members))
        ]
        assert len(link_strings) in [5, 6]  # Testing scope can include a profile link
        assert len(members_link_strings) == 5
        assert "/catalogues/cats:vocab-cats" in link_strings
        assert "/catalogues/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cat2" in link_strings
        assert "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cats/collections/cats:vocab-cat2" in link_strings
        assert "/catalogues/cats:vocab-cats/collections" in members_link_strings
        assert "/catalogues/cats:vocab-cat1/collections" in members_link_strings
        assert "/catalogues/cats:vocab-cat2/collections" in members_link_strings
        assert (
            "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1/items"
            in members_link_strings
        )
        assert (
            "/catalogues/cats:vocab-cats/collections/cats:vocab-cat2/items"
            in members_link_strings
        )

    def test_catalogues_object_endpoint_accessible(self, issue_236_client):
        """
        Test that the /catalogues/{catalogueId} endpoint is accessible and returns data.
        """
        # First get the listing to extract the link - this returns a single triple w/ mediatype=text/turtle
        # with annotated form, as iris for the children are "discovered" as part of link generation, they are included
        # in the annotated payload. Their inclusion is unnecessary and could be removed.
        listing_response = issue_236_client.get("/catalogues/cats:vocab-cats")
        g = Graph()
        g.parse(data=listing_response.text, format="turtle")
        link_strings = [str(link) for link in list(g.objects(predicate=PREZ.link))]
        members_link_strings = [
            str(link) for link in list(g.objects(predicate=PREZ.members))
        ]
        assert len(link_strings) == 5
        assert len(members_link_strings) == 5
        assert "/catalogues/cats:vocab-cats" in link_strings
        assert "/catalogues/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cat2" in link_strings
        assert "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cats/collections/cats:vocab-cat2" in link_strings
        assert "/catalogues/cats:vocab-cats/collections" in members_link_strings
        assert "/catalogues/cats:vocab-cat1/collections" in members_link_strings
        assert "/catalogues/cats:vocab-cat2/collections" in members_link_strings
        assert (
            "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1/items"
            in members_link_strings
        )
        assert (
            "/catalogues/cats:vocab-cats/collections/cats:vocab-cat2/items"
            in members_link_strings
        )

    def test_nested_collections_listing_has_links(self, issue_236_client):
        """
        Test that /catalogues/{catalogueId}/collections returns items with links.

        This tests hierarchy level 2, which should also have proper links generated.
        """
        response = issue_236_client.get("/catalogues/cats:vocab-cats/collections")
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        g = Graph()
        g.parse(data=response.text, format="turtle")
        link_strings = [str(link) for link in list(g.objects(predicate=PREZ.link))]
        members_link_strings = [
            str(link) for link in list(g.objects(predicate=PREZ.members))
        ]
        assert len(link_strings) in [4, 5]  # Testing scope can include a profile link
        assert len(members_link_strings) == 4
        assert "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cats/collections/cats:vocab-cat2" in link_strings
        assert "/catalogues/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cat2" in link_strings
        assert "/catalogues/cats:vocab-cat1/collections" in members_link_strings
        assert "/catalogues/cats:vocab-cat2/collections" in members_link_strings
        assert (
            "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1/items"
            in members_link_strings
        )
        assert (
            "/catalogues/cats:vocab-cats/collections/cats:vocab-cat2/items"
            in members_link_strings
        )

    def test_catalogues_cat1(self, issue_236_client):
        """
        Test that the /catalogues/{catalogueId} endpoint is accessible and returns data.
        """
        # First get the listing to extract the link - this returns a single triple w/ mediatype=text/turtle
        # with annotated form, as iris for the children are "discovered" as part of link generation, they are included
        # in the annotated payload. Their inclusion is unnecessary and could be removed.
        listing_response = issue_236_client.get("/catalogues/cats:vocab-cat1")
        g = Graph()
        g.parse(data=listing_response.text, format="turtle")
        link_strings = [str(link) for link in list(g.objects(predicate=PREZ.link))]
        members_link_strings = [
            str(link) for link in list(g.objects(predicate=PREZ.members))
        ]
        assert len(link_strings) == 4
        assert len(members_link_strings) == 4
        assert "/catalogues/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cat1/collections/vocabs:vocab1" in link_strings
        assert "/catalogues/cats:vocab-cat1/collections/vocabs:vocab2" in link_strings
        assert "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1" in link_strings
        assert "/catalogues/cats:vocab-cat1/collections" in members_link_strings
        assert (
            "/catalogues/cats:vocab-cat1/collections/vocabs:vocab1/items"
            in members_link_strings
        )
        assert (
            "/catalogues/cats:vocab-cat1/collections/vocabs:vocab2/items"
            in members_link_strings
        )
        assert (
            "/catalogues/cats:vocab-cats/collections/cats:vocab-cat1/items"
            in members_link_strings
        )
