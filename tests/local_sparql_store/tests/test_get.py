import pytest
import subprocess
import httpx
from pathlib import Path
from time import sleep

LOCAL_SPARQL_STORE = Path(__file__).parent.parent / "store.py"


@pytest.fixture(scope="module")
def store_instance(request):
    print("Run Local SPARQL Store")
    port = "3040"
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", port])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    return port


def test_home(store_instance):
    r = httpx.get(f"http://localhost:{store_instance}/")
    assert r.status_code == 200


def test_vocprez_home(store_instance):
    r = httpx.get(f"http://localhost:{store_instance}/vocprez")
    assert r.status_code == 200


def test_spaceprez_home(store_instance):
    r = httpx.get(f"http://localhost:{store_instance}/spaceprez")
    assert r.status_code == 200


def test_unknown_endpoint(store_instance):
    r = httpx.get(f"http://localhost:{store_instance}/xxx")
    assert r.status_code == 404


def test_vocprez_query_good(store_instance):
    r = httpx.get(
        f"http://localhost:{store_instance}/vocprez"
        "?query=PREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0AASK%0AWHERE%20{%0A%20%20%20%20%3Fc%20a%20skos%3AConcept%20%3B%0A%20%20%20%20%20%20%20skos%3AprefLabel%20%3Fpl%20.%0A}%0ALIMIT%205"
    )
    assert r.status_code == 200


def test_vocprez_query_bad(store_instance):
    r = httpx.get(
        f"http://localhost:{store_instance}/vocprez"
        "?query=ddddPREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0AASK%0AWHERE%20{%0A%20%20%20%20%3Fc%20a%20skos%3AConcept%20%3B%0A%20%20%20%20%20%20%20skos%3AprefLabel%20%3Fpl%20.%0A}%0ALIMIT%205"
    )
    assert r.status_code == 400
    assert r.text.startswith("Your SPARQL query could not be interpreted")
