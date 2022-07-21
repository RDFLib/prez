# these tests will not work with the Local SPARQL Store. Must have Fuseki etc. running as a back-end
import os

import shutil
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

PREZ_DIR = Path(__file__).parent.parent.absolute() / "prez"


@pytest.fixture(scope="module")
def vp_test_client(request):
    print("\nDoing config setup")
    # preserve original config file
    shutil.copyfile(PREZ_DIR / "config.py", PREZ_DIR / "config.py.original")

    # alter config file contents
    with open(PREZ_DIR / "config.py") as f:
        config = f.read()
        config = config.replace("Default Prez", "Test Prez")
        config = config.replace("Default VocPrez", "Test VocPrez")
        config = config.replace('["VocPrez", "SpacePrez"]', '["VocPrez"]')
        config = config.replace(
            '"VOCPREZ_SPARQL_ENDPOINT", ""',
            '"VOCPREZ_SPARQL_ENDPOINT", "http://localhost:3030/vocprez"',
        )

    # write altered config contents to config.py
    with open(PREZ_DIR / "config.py", "w") as f:
        f.truncate(0)
        f.write(config)

    def teardown():
        print("\nDoing teardown")

        # remove altered config file
        os.unlink(PREZ_DIR / "config.py")

        # restore original file
        shutil.copyfile(PREZ_DIR / "config.py.original", PREZ_DIR / "config.py")
        os.unlink(PREZ_DIR / "config.py.original")

    request.addfinalizer(teardown)

    from prez.app import app

    return TestClient(app)


def test_service_description(vp_test_client):
    r = vp_test_client.get(
        "/sparql",
        headers={"Accept": "application/rdf+xml"}
    )
    assert r.text.startswith('<?xml version="1.0" encoding="utf-8"?>')

    r = vp_test_client.get(
        "/sparql",
        headers={"Accept": "application/n-triples"}
    )
    assert r.text.startswith('<')


def test_raw_query_get_header(vp_test_client):
    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                     PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                     SELECT (COUNT(?c) AS ?count)
                     WHERE {
                        ?c a skos:Concept .
                     }
                     """
        },
        headers={"Accept": "application/sparql-results+json"}
    )
    # print(r.json().get("results").get("bindings")[0].get("count").get("value"))
    assert '"datatype":"http://www.w3.org/2001/XMLSchema#integer","value"' in r.text

    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                     PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                     SELECT (COUNT(?c) AS ?count)
                     WHERE {
                        ?c a skos:Concept .
                     }
                     """
        },
        headers={"Accept": "application/sparql-results+xml"}
    )
    assert '<literal datatype="http://www.w3.org/2001/XMLSchema#integer">' in r.text

    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    
                    CONSTRUCT {
                      ?c a skos:Concept .
                    }
                    WHERE {
                        ?c a skos:Concept .
                    }
                    LIMIT 3
                     """
        },
        headers={"Accept": "text/turtle"}
    )
    assert "a skos:Concept" in r.text

    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                    CONSTRUCT {
                      ?c a skos:Concept .
                    }
                    WHERE {
                        ?c a skos:Concept .
                    }
                    LIMIT 3
                     """
        },
        headers={"Accept": "application/ld+json"}
    )
    assert type(r.json()[0]["@id"]) == str


def test_raw_query_get_accept_param(vp_test_client):
    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                     PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                     SELECT (COUNT(?c) AS ?count)
                     WHERE {
                        ?c a skos:Concept .
                     }
                     """,
            "Accept": "application/sparql-results+json"
        }
    )
    # print(r.json().get("results").get("bindings")[0].get("count").get("value"))
    assert '"datatype":"http://www.w3.org/2001/XMLSchema#integer","value"' in r.text

    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                     PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                     SELECT (COUNT(?c) AS ?count)
                     WHERE {
                        ?c a skos:Concept .
                     }
                     """,
            "Accept": "application/sparql-results+xml"
        }
    )
    assert '<literal datatype="http://www.w3.org/2001/XMLSchema#integer">' in r.text

    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                    CONSTRUCT {
                      ?c a skos:Concept .
                    }
                    WHERE {
                        ?c a skos:Concept .
                    }
                    LIMIT 3
                     """,
            "Accept": "text/turtle"
        }
    )
    assert "a skos:Concept" in r.text

    r = vp_test_client.get(
        "/sparql",
        params={
            "query": """
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                    CONSTRUCT {
                      ?c a skos:Concept .
                    }
                    WHERE {
                        ?c a skos:Concept .
                    }
                    LIMIT 3
                     """,
            "Accept": "application/ld+json"
        }
    )
    assert type(r.json()[0]["@id"]) == str


def test_raw_query_post_header(vp_test_client):
    r = vp_test_client.post(
        "/sparql",
        data="""
             PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

             SELECT (COUNT(?c) AS ?count)
             WHERE {
                ?c a skos:Concept .
             }
             """,
        headers={"Accept": "application/sparql-results+json"}
    )
    # print(r.json().get("results").get("bindings")[0].get("count").get("value"))
    assert '"datatype":"http://www.w3.org/2001/XMLSchema#integer","value"' in r.text

    r = vp_test_client.post(
        "/sparql",
        data="""
             PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

             SELECT (COUNT(?c) AS ?count)
             WHERE {
                ?c a skos:Concept .
             }
             """,
        headers={"Accept": "application/sparql-results+xml"}
    )
    assert '<literal datatype="http://www.w3.org/2001/XMLSchema#integer">' in r.text

    r = vp_test_client.post(
        "/sparql",
        data="""
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            CONSTRUCT {
              ?c a skos:Concept .
            }
            WHERE {
                ?c a skos:Concept .
            }
            LIMIT 3
             """,
        headers={"Accept": "text/turtle"}
    )
    # assert '<literal datatype="http://www.w3.org/2001/XMLSchema#integer">' in r.text
    assert "a skos:Concept" in r.text

    r = vp_test_client.post(
        "/sparql",
        data="""
             PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

             SELECT (COUNT(?c) AS ?count)
             WHERE {
                ?c a skos:Concept .
             }
             """,
        headers={"Accept": "application/ld+json"}
    )
    assert type(r.json()[0]["@id"]) == str
