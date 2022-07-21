import pytest
import subprocess
import httpx
from pathlib import Path
from time import sleep

LOCAL_SPARQL_STORE = Path(__file__).parent.parent / "store.py"


@pytest.fixture(scope="module")
def store_instance(request):
    print("Run Local SPARQL Store")
    port = "3041"
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", port])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    return port


def test_home(store_instance):
    r = httpx.post(f"http://localhost:{store_instance}")
    assert r.status_code == 200


def test_vocprez_query(store_instance):
    q = """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        SELECT (COUNT(?cs) AS ?c)
        WHERE {
            ?cs a skos:ConceptScheme 
        }
        """
    r = httpx.post(f"http://localhost:{store_instance}/vocprez", data=q)
    assert r.status_code == 200
    assert r.json()["results"]["bindings"][0]["c"]["value"] == "2"


def test_spaceprez_query(store_instance):
    r = httpx.post(
        f"http://localhost:{store_instance}/spaceprez",
        data="SELECT * WHERE {?c a dcat:Dataset}",
    )
    assert r.status_code == 200


def test_unknown_endpoint(store_instance):
    r = httpx.post(f"http://localhost:{store_instance}/xxx")
    assert r.status_code == 404
