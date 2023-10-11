import math


def order_urls(order: list[str], values: list[str]):
    """Order a set of URL values based on a preferred order.

    :param order: The preferred order - used to see if the URL values match it with a str.startswith check.
    :param values: The URL values.

    >>> preferred_order = [
    >>>     "/v/vocab",
    >>>     "/v/collection",
    >>>     "/s/datasets",
    >>>     "/c/catalogs"
    >>> ]
    >>> urls = [
    >>>     "/s/datasets/blah",
    >>>     "/object/blah",
    >>>     "/v/collection/123",
    >>>     "/c/catalogs/321",
    >>>     "/v/vocab/some-scheme"
    >>> ]
    >>> sorted_urls = order_urls(preferred_order, urls)
    >>> assert sorted_urls == [
    >>>     "/v/vocab/some-scheme",
    >>>     "/v/collection/123",
    >>>     "/s/datasets/blah",
    >>>     "/c/catalogs/321",
    >>>     "/object/blah"
    >>> ]
    """
    order_dict = {url: i for i, url in enumerate(order)}
    # Set values matched with None to infinity.
    order_dict.update({None: math.inf})
    return sorted(
        values,
        key=lambda url: order_dict[next((o for o in order if url.startswith(o)), None)],
    )
