import pytest

from prez.services.connegp_service import ConnegpParser


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
            {"Accept-Profile": "ogc"},
            {},
            [("<https://prez.dev/OGCRecordsProfile>", 1.0)],
            None  # Test that a resolvable token is resolved
        ]
    ]
)
def test_connegp(headers, params, expected_profiles, expected_mediatypes):
    parser = ConnegpParser(headers=headers, params=params)
    parsed_profiles = parser.get_requested_profiles()
    parsed_mediatypes = parser.get_requested_mediatypes()

    assert parsed_profiles == expected_profiles
    assert parsed_mediatypes == expected_mediatypes
