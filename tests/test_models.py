from models.spaceprez_item import Item

import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from time import sleep

PREZ_DIR = Path(__file__).parent.parent.absolute() / "prez"
LOCAL_SPARQL_STORE = Path(Path(__file__).parent / "local_sparql_store/store.py")
sys.path.insert(0, str(PREZ_DIR.parent.absolute()))
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def sp_test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3032"])
    sleep(1)
    print("\nDoing config setup")
    # preserve original config file
    shutil.copyfile(PREZ_DIR / "config.py", PREZ_DIR / "config.py.original")

    # alter config file contents
    with open(PREZ_DIR / "config.py") as f:
        config = f.read()
        config = config.replace("Default Prez", "Test Prez")
        config = config.replace("Default SpacePrez", "Test SpacePrez")
        config = config.replace('["VocPrez", "SpacePrez"]', '["SpacePrez"]')
        config = config.replace(
            '"SPACEPREZ_SPARQL_ENDPOINT", ""',
            '"SPACEPREZ_SPARQL_ENDPOINT", "http://localhost:3032/spaceprez"',
        )

    # write altered config contents to config.py
    with open(PREZ_DIR / "config.py", "w") as f:
        f.truncate(0)
        f.write(config)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

        # remove altered config file
        os.unlink(PREZ_DIR / "config.py")

        # restore original file
        shutil.copyfile(PREZ_DIR / "config.py.original", PREZ_DIR / "config.py")
        os.unlink(PREZ_DIR / "config.py.original")

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app

    return TestClient(app)


def test_feature_item():
    pass
    item = Item(feature_uri="test")
    # item.populate()
    # assert item.uri == "http://example.com/test"
    # assert item.feature_classes == ["http://example.com/Class"]
