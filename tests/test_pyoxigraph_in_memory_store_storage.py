import logging

from prez.dependencies import get_pyoxi_store


def test_pyoxigraph_in_memory_store_storage(caplog):
    caplog.set_level(logging.INFO)
    get_pyoxi_store()

    assert "Using in-memory pyoxigraph data store" in caplog.text
