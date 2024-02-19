import pytest

from prez.services.connegp_service import ConnegpParser


@pytest.mark.parametrize(
    "headers, params, expected_profiles, expected_mediatypes",
    [
        [
            {"Accept-Profile": "<default>, <alternate>;q=0.9"},
            {"_media": "text/anot+turtle, text/turtle;q=0.9"},
            [("default", 1.0), ("alternate", 0.9)],
            [("text/anot+turtle", 1.0), ("text/turtle", 0.9)]
        ],
        [
            {"Accept-Profile": "<alternate>;q=0.9, <default>"},
            {"_media": "text/turtle;q=0.9, text/anot+turtle"},
            [("default", 1.0), ("alternate", 0.9)],
            [("text/anot+turtle", 1.0), ("text/turtle", 0.9)]
        ]
    ]
)
def test_connegp(headers, params, expected_profiles, expected_mediatypes):
    parser = ConnegpParser(headers=headers, params=params)
    parsed_profiles = parser.get_requested_profiles()
    parsed_mediatypes = parser.get_requested_mediatypes()

    assert parsed_profiles == expected_profiles
    assert parsed_mediatypes == expected_mediatypes
