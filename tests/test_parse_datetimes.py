from datetime import datetime, timezone
from typing import Optional, Tuple

import pytest

from prez.models.query_params import parse_datetime


@pytest.mark.parametrize(
    "input_str, expected_output",
    [
        # Full RFC 3339 date-time strings
        (
            "2018-02-12T23:20:50Z",
            (datetime(2018, 2, 12, 23, 20, 50, tzinfo=timezone.utc), None),
        ),
        (
            "2018-02-12T23:20:50+00:00",
            (datetime(2018, 2, 12, 23, 20, 50, tzinfo=timezone.utc), None),
        ),
        (
            "2018-02-12T23:20:50-07:00",
            (datetime(2018, 2, 13, 6, 20, 50, tzinfo=timezone.utc), None),
        ),
        (
            "2018-02-12T23:20:50.123Z",
            (datetime(2018, 2, 12, 23, 20, 50, 123000, tzinfo=timezone.utc), None),
        ),
        # RFC 3339 date strings (if your function supports them)
        ("2018-02-12", (datetime(2018, 2, 12, 0, 0, 0), None)),
        # Intervals
        (
            "2018-02-12T23:20:50Z/2018-03-18T12:31:12Z",
            (
                datetime(2018, 2, 12, 23, 20, 50, tzinfo=timezone.utc),
                datetime(2018, 3, 18, 12, 31, 12, tzinfo=timezone.utc),
            ),
        ),
        (
            "../2018-03-18T12:31:12Z",
            ("..", datetime(2018, 3, 18, 12, 31, 12, tzinfo=timezone.utc)),
        ),
        (
            "2018-02-12T23:20:50Z/..",
            (datetime(2018, 2, 12, 23, 20, 50, tzinfo=timezone.utc), ".."),
        ),
        (
            "/2018-03-18T12:31:12Z",
            (None, datetime(2018, 3, 18, 12, 31, 12, tzinfo=timezone.utc)),
        ),
        (
            "2018-02-12T23:20:50Z/",
            (datetime(2018, 2, 12, 23, 20, 50, tzinfo=timezone.utc), None),
        ),
        # Edge cases
        (
            "2018-02-12T23:20:50+01:00",
            (datetime(2018, 2, 12, 22, 20, 50, tzinfo=timezone.utc), None),
        ),
        (
            "2018-02-12t23:20:50z",  # Testing lower case 't' and 'z' if supported
            (datetime(2018, 2, 12, 23, 20, 50, tzinfo=timezone.utc), None),
        ),
    ],
)
def test_parse_datetime_valid(
    input_str: str, expected_output: Tuple[Optional[datetime], Optional[datetime]]
):
    parsed = parse_datetime(input_str)
    assert parsed == expected_output


@pytest.mark.parametrize(
    "input_str",
    [
        # Invalid cases
        "invalid_datetime",
        # "2018-02-12 23:20:50Z",  # Space instead of 'T'
        # "2018-02-12T23:20:50",  # Missing timezone
        "2018-02-12T23:20:50ZZ",  # Invalid timezone
        # "2018-02-12T23:20:50+0000",  # Invalid timezone format
        "2018-02-12T23:20:50Z/2018-03-18T12:31:12Z/extra",  # Too many parts
        "../..",  # Both parts open
        "2018-13-12T00:00:00Z",  # Invalid month
        "2018-02-30T00:00:00Z",  # Invalid day
        "2018-02-12T24:00:00Z",  # Invalid hour
        "2018-02-12T23:60:00Z",  # Invalid minute
        "2018-02-12T23:59:61Z",  # Invalid second (60 is valid for leap seconds)
    ],
)
def test_parse_datetime_invalid(input_str: str):
    with pytest.raises(ValueError):
        parse_datetime(input_str)


def test_parse_datetime_none_input():
    with pytest.raises(AttributeError):
        parse_datetime(None)
