import json
from pathlib import Path

import pytest

cql_time_filenames = [
    "example20.json",  # t_before
    "example21.json",  # t_after
    "example54.json",  # t_before
    "example53.json",  # t_after
]

cql_time_generated_queries = [Path(name).with_suffix(".rq") for name in cql_time_filenames]


@pytest.mark.parametrize(
    "cql_json_filename, output_query_filename",
    [i for i in (zip(cql_time_filenames, cql_time_generated_queries))]
)
def test_simple_post(client, cql_json_filename, output_query_filename):
    cql_json_path = Path(__file__).parent.parent / f"test_data/cql/input/{cql_json_filename}"
    cql_json = json.loads(cql_json_path.read_text())
    output_query = (Path(
        __file__).parent.parent / f"test_data/cql/expected_generated_queries/{output_query_filename}").read_text()
    headers = {"content-type": "application/json", "accept": "application/sparql-query"}
    response = client.post("/cql", json=cql_json, headers=headers)
    assert response.text == output_query
