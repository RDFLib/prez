import logging

import pytest
from pyoxigraph import Store

from prez import dependencies as deps
from prez.cache import store as in_memory_store
from prez.dependencies import get_pyoxi_store


def test_pyoxigraph_in_memory_store_selected(monkeypatch):
    """The default repository type resolves to the process's in-memory store."""
    monkeypatch.setattr(deps.settings, "sparql_repo_type", "pyoxigraph_memory")
    selected = get_pyoxi_store()
    assert isinstance(selected, Store)
    assert selected is in_memory_store


@pytest.mark.parametrize("repo_type", ["pyoxigraph_memory", "remote", "oxrdflib"])
def test_pyoxigraph_store_selection_does_not_log(repo_type, monkeypatch, caplog):
    """Selecting the store is silent.

    It is a per-request dependency of get_data_repo, so logging here put a line in
    the log for every request, including for repository types that never touch a
    pyoxigraph store. Which repository is in use is announced once at startup.
    """
    monkeypatch.setattr(deps.settings, "sparql_repo_type", repo_type)
    with caplog.at_level(logging.INFO, logger="prez.dependencies"):
        caplog.clear()
        get_pyoxi_store()
    assert caplog.text == ""
