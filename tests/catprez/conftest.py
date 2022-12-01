import os
from pathlib import Path
import sys

import pytest

os.environ["CATPREZ_SPARQL_ENDPOINT"] = "http://localhost:3033/catprez"
PREZ_DIR = Path(__file__).parent.parent.parent.absolute() / "prez"
os.environ["PREZ_DIR"] = str(PREZ_DIR)
os.environ["LOCAL_SPARQL_STORE"] = str(
    Path(Path(__file__).parent.parent / "local_sparql_store/store.py")
)

sys.path.insert(0, str(PREZ_DIR.parent.absolute()))


# @pytest.fixture(autouse=True)
# def change_test_dir(request, monkeypatch):
#     monkeypatch.chdir(request.fspath.dirname)
