import tempfile
import logging
from pathlib import Path

import pytest

from prez.dependencies import get_pyoxi_store
from prez.config import settings


@pytest.fixture(scope="function")
def tmp_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        yield tmp_path

    assert not tmp_path.exists()


@pytest.fixture(autouse=True)
def setup_settings(tmp_path: Path):
    settings.pyoxigraph_data_dir = str(tmp_path)
    settings.sparql_repo_type = "pyoxigraph_persistent"


@pytest.fixture(scope="function")
def non_existent_data_dir():
    settings.pyoxigraph_data_dir = "non-existent-data-dir-for-testing"
    return Path(settings.pyoxigraph_data_dir)


def test_pyoxigraph_store_disk_storage_non_existent_data_dir(
    non_existent_data_dir: Path,
):
    assert not non_existent_data_dir.exists()
    with pytest.raises(FileNotFoundError):
        get_pyoxi_store()


def test_pyoxigraph_store_disk_storage_existent_data_dir(tmp_path: Path, caplog):
    caplog.set_level(logging.INFO)
    assert tmp_path.exists()
    get_pyoxi_store()

    assert "Using pyoxigraph data store" in caplog.text
