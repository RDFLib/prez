import json
from pathlib import Path
from urllib.parse import quote_plus

import pytest


cql_filenames = [
        "example01.json",
        "example02.json",
        "example03.json",
        "example05a.json",
        "example05b.json",
        "example06b.json",
        "example09.json",
        "example10.json",
        "example11.json",
        "example12.json",
        "example14.json",
        "example15.json",
        "example17.json",
        "example29.json",
        "example31.json",
        "example32.json",
        "example33.json",
        "example34.json",
        "example35.json",
        "example39.json"
    ]

# @pytest.mark.parametrize(
#     "cql_json_filename",
#     cql_filenames
# )
# def test_simple_post(client, cql_json_filename):
#     cql_json_path = Path(__file__).parent.parent / f"test_data/cql/input/{cql_json_filename}"
#     cql_json = json.loads(cql_json_path.read_text())
#     headers = {"content-type": "application/json"}
#     response = client.post("/cql", json=cql_json, headers=headers)
#     assert response.status_code == 200

@pytest.mark.parametrize(
    "cql_json_filename",
    cql_filenames
)
def test_simple_get(client, cql_json_filename):
    cql_json_path = Path(__file__).parent.parent / f"test_data/cql/input/{cql_json_filename}"
    cql_json = json.loads(cql_json_path.read_text())
    query_string = quote_plus(json.dumps(cql_json))
    response = client.get(
        f"/cql?filter={query_string}"
    )
    assert response.status_code == 200


# def test_intersects_post(client):
#     cql_json_path = Path(__file__).parent.parent / f"test_data/cql/input/geo_intersects.json"
#     cql_json = json.loads(cql_json_path.read_text())
#     headers = {"content-type": "application/json"}
#     response = client.post("/cql", json=cql_json, headers=headers)
#     assert response.status_code == 200


def test_intersects_get(client):
    cql_json_path = Path(__file__).parent.parent / f"test_data/cql/input/geo_intersects.json"
    cql_json = json.loads(cql_json_path.read_text())
    query_string = quote_plus(json.dumps(cql_json))
    response = client.get(
        f"/cql?filter={query_string}&_mediatype=application/sparql-query"
    )
    assert response.status_code == 200
