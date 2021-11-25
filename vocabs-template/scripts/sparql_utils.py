from typing import List, Dict

import httpx

from config import *


def sparql_query(q: str) -> List[Dict]:
    endpoint = ""
    if DB_TYPE == "fuseki":
        endpoint = f"{DB_BASE_URI}/query"
    elif DB_TYPE == "graphdb":
        endpoint = f"{DB_BASE_URI}"
    else:  # unsupported db type
        raise ValueError(
            "Unsupported DB type. Supported types are: 'fuseki', 'graphdb'."
        )

    response = httpx.get(
        endpoint,
        params={"query": q},
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/sparql-query",
        },
        auth=(DB_USERNAME, DB_PASSWORD),
    )
    if 200 <= response.status_code < 300:
        return response.json()["results"]["bindings"]
    else:
        raise Exception(
            f"SPARQL query error code {response.status_code}: {response.text}"
        )


def sparql_update(q: str) -> bool:
    endpoint = ""
    if DB_TYPE == "fuseki":
        endpoint = f"{DB_BASE_URI}/update"
    elif DB_TYPE == "graphdb":
        endpoint = f"{DB_BASE_URI}/statements"
    else:  # unsupported db type
        raise ValueError(
            "Unsupported DB type. Supported types are: 'fuseki', 'graphdb'."
        )

    response = httpx.post(
        endpoint,
        data={"update": q},
        # headers={
        #     "Content-Type": "application/sparql-update",
        # },
        auth=(DB_USERNAME, DB_PASSWORD),
    )
    if 200 <= response.status_code < 300:
        return True
    else:
        raise Exception(
            f"SPARQL update error code {response.status_code}: {response.text}"
        )


def sparql_insert_graph(graph_uri: str, graph_content: bytes) -> bool:
    params = {}
    endpoint = ""
    if DB_TYPE == "fuseki":
        params = {"graph": graph_uri}
        endpoint = f"{DB_BASE_URI}/data"
    elif DB_TYPE == "graphdb":
        params = {"context": f"<{graph_uri}>"}
        endpoint = f"{DB_BASE_URI}/statements"
    else:  # unsupported db type
        raise ValueError(
            "Unsupported DB type. Supported types are: 'fuseki', 'graphdb'."
        )

    response = httpx.post(
        endpoint,
        params=params,
        headers={
            "Content-Type": "text/turtle",
        },
        content=graph_content,
        auth=(DB_USERNAME, DB_PASSWORD),
        timeout=20.0,
    )
    if 200 <= response.status_code < 300:
        return True
    else:
        raise Exception(
            f"SPARQL graph insert error code {response.status_code}: {response.text}"
        )


def sparql_construct(q: str) -> str:
    endpoint = ""
    if DB_TYPE == "fuseki":
        endpoint = f"{DB_BASE_URI}/query"
    elif DB_TYPE == "graphdb":
        endpoint = f"{DB_BASE_URI}"
    else:  # unsupported db type
        raise ValueError(
            "Unsupported DB type. Supported types are: 'fuseki', 'graphdb'."
        )

    response = httpx.get(
        endpoint,
        params={"query": q},
        headers={
            "Accept": "text/turtle",
            "Content-Type": "application/sparql-query",
        },
        auth=(DB_USERNAME, DB_PASSWORD),
    )
    if 200 <= response.status_code < 300:
        return response.text
    else:
        raise Exception(
            f"SPARQL query error code {response.status_code}: {response.text}"
        )
