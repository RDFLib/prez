import pytest

from prez.url import order_urls


@pytest.mark.parametrize(
    "order, urls, expected_urls",
    [
        [
            ["/v/vocab", "/v/collection", "/s/datasets", "/c/catalogs"],
            ["/s/datasets/blah", "/v/collection/123", "/c/catalogs/321"],
            ["/v/collection/123", "/s/datasets/blah", "/c/catalogs/321"],
        ],
        [
            ["/v/vocab", "/v/collection", "/s/datasets", "/c/catalogs"],
            [
                "/s/datasets/blah",
                "/object/blah",
                "/v/collection/123",
                "/c/catalogs/321",
                "/v/vocab/some-scheme",
            ],
            [
                "/v/vocab/some-scheme",
                "/v/collection/123",
                "/s/datasets/blah",
                "/c/catalogs/321",
                "/object/blah",
            ],
        ],
    ],
)
def test_url_order(order: list[str], urls: list[str], expected_urls: list[str]):
    ordered_urls = order_urls(order, urls)
    assert ordered_urls == expected_urls
