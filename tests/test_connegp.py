from pathlib import Path

import pytest
from pyoxigraph import Store
from rdflib import Graph

from prez.services.connegp_service import ConnegpParser


@pytest.fixture(scope="module")
def test_store() -> Store:
    store = Store()
    profiles = Path(__file__).parent / "data" / "profiles" / "remote_profile.ttl"
    store.load(profiles, mime_type="text/turtle")
    return store


@pytest.fixture(scope="module")
def test_prefix_graph():
    graph = Graph(bind_namespaces="rdflib")
    graph.bind("ex", "http://example.com/")
    return graph


@pytest.mark.parametrize(
    "headers, params, expected_profiles, expected_mediatypes",
    [
        [
            {"Accept-Profile": "<default>, <alternate>;q=0.9"},
            {"_media": "text/anot+turtle, text/turtle;q=0.9"},
            [("<default>", 1.0), ("<alternate>", 0.9)],
            [("text/anot+turtle", 1.0), ("text/turtle", 0.9)]  # Test that profiles/mediatypes are extracted
        ],
        [
            {"Accept-Profile": "<alternate>;q=0.9, <default>"},
            {"_media": "text/turtle;q=0.9, text/anot+turtle"},
            [("<default>", 1.0), ("<alternate>", 0.9)],
            [("text/anot+turtle", 1.0), ("text/turtle", 0.9)]  # Test that they are prioritized correctly
        ],
        [
            {"Accept": "application/json"},
            {"_media": "text/turtle"},
            None,
            [("text/turtle", 1.0)]  # Test that QSA is preferred over HTTP for mediatypes
        ],
        [
            {"Accept-Profile": "<default>"},
            {"_profile": "<alternate>"},
            [("<alternate>", 1.0)],
            None  # Test that QSA is preferred over HTTP for profiles
        ],
        [
            {"Accept-Profile": "invalid-token"},
            {},
            [("invalid-token", 1.0)],
            None  # Test that an unresolvable token is returned as is
        ],
        [
            {"Accept-Profile": "exprof"},
            {},
            [("<https://example.com/profile>", 1.0)],
            None  # Test that a resolvable token is resolved
        ],
        [
            {"Accept-Profile": "invalid:profile"},
            {},
            [("invalid:profile", 1.0)],
            None  # Test that an unresolvable curie is returned as is
        ],
        [
            {"Accept-Profile": "ex:profile"},
            {},
            [("<http://example.com/profile>", 1.0)],
            None  # Test that a resolvable curie is resolved
        ]
    ]
)
def test_connegp(headers, params, expected_profiles, expected_mediatypes, test_store, test_prefix_graph):
    parser = ConnegpParser(headers=headers, params=params, system_store=test_store, prefix_graph=test_prefix_graph)
    parsed_profiles = parser.get_requested_profiles()
    parsed_mediatypes = parser.get_requested_mediatypes()

    assert parsed_profiles == expected_profiles
    assert parsed_mediatypes == expected_mediatypes
