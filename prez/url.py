import math


def order_urls(order: list[str], values: list[str]):
    order_dict = {url: i for i, url in enumerate(order)}
    # Set values matched with None to infinity.
    order_dict.update({None: math.inf})
    return sorted(
        values,
        key=lambda url: order_dict[next((o for o in order if url.startswith(o)), None)],
    )
