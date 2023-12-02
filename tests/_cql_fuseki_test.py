# NB these tests require a running Fuseki server with the appropriate data loaded. The tests will fail if the server is not
# running or the data is not loaded. ALL data in the test_data directory is required.
import json
import os
import time
from pathlib import Path
from urllib.parse import quote_plus

import httpx
import pytest
from rdflib import Graph
from starlette.testclient import TestClient

from prez.app import assemble_app


def docker_run():
    command = (
        "docker run -d --name fuseki -p 3030:3030 "
        "-v $(pwd)/cql-testing-fuseki-config.ttl:/fuseki/config.ttl "
        "-v $(pwd)/../test_data:/rdf "
        "-e ADMIN_PASSWORD=pw "
        "ghcr.io/zazuko/fuseki-geosparql:v3.3.1"
    )
    os.system(command)


def healthcheck(url, interval, timeout, retries):
    for _ in range(retries):
        try:
            response = httpx.get(url, timeout=timeout)
            if response.status_code == 200:
                print("Service is healthy")
                return True
        except httpx.RequestError:
            pass
        time.sleep(interval)
    print("Service is not healthy")
    return False


# if not healthcheck("http://localhost:3030", 1, 3, 1):
#     docker_run()
# online = False
# while not online:
#     online = healthcheck("http://localhost:3030", 5, 10, 3)


@pytest.fixture(scope="module")
def client_fuseki() -> TestClient:
    app = assemble_app()
    with TestClient(app) as c:
        yield c


# cql_filenames = []
#
# @pytest.mark.parametrize(
#     "cql_json_filename",
#     cql_filenames
# )
def spatial_functions(client_fuseki):
    file = Path(__file__).parent.parent / "test_data/cql/input/geo_contains.json"
    with file.open() as f:
        cql = json.load(f)
    cql_str = json.dumps(cql)
    cql_encoded = quote_plus(cql_str)
    response = client_fuseki.get(
        f"/cql?filter={cql_encoded}&_mediatype=application/sparql-query"
    )
    query = response.text
    response_graph = Graph().parse(data=response.text)
    print("x")
