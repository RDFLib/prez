import asyncio
import logging
from typing import Dict, Tuple, Union
from typing import List

import httpx
from httpx import Client, AsyncClient
from httpx import Response as httpxResponse
from rdflib import Namespace, Graph
from starlette.requests import Request

from prez.config import settings

PREZ = Namespace("https://prez.dev/")


async_client = AsyncClient(
    auth=(settings.sparql_username, settings.sparql_password)
    if settings.sparql_username
    else None,
)

client = Client(
    auth=(settings.sparql_username, settings.sparql_password)
    if settings.sparql_username
    else None,
)


log = logging.getLogger(__name__)

TIMEOUT = 30.0


def sparql_query_non_async(query: str) -> Tuple[bool, Union[List, Dict]]:
    """Executes a SPARQL SELECT query for a single SPARQL endpoint"""
    response: httpxResponse = client.post(
        settings.sparql_endpoint,
        data=query,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/sparql-query",
        },
        timeout=TIMEOUT,
    )
    if 200 <= response.status_code < 300:
        return True, response.json()["results"]["bindings"]
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
        }


def sparql_ask_non_async(query: str):
    """Returns True if the provided triple pattern exists in the graph, otherwise False"""
    response: httpxResponse = client.post(
        settings.sparql_endpoint,
        data={"query": query},
        headers={
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=TIMEOUT,
    )
    if 200 <= response.status_code < 300:
        return True, response.json()["boolean"]
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
        }


async def sparql(request: Request):
    """Sends a starlette Request object (containing a SPARQL query in the URL parameters) to a proxied SPARQL
    endpoint."""
    url = httpx.URL(
        url=settings.sparql_endpoint, query=request.url.query.encode("utf-8")
    )
    headers = []
    for header in request.headers.raw:
        if header[0] != b"host":
            headers.append(header)
    headers.append((b"host", str(url.host).encode("utf-8")))
    rp_req = async_client.build_request(
        request.method, url, headers=headers, content=request.stream()
    )
    return await async_client.send(rp_req, stream=True)


async def send_query(query: str, mediatype="text/turtle"):
    """Sends a SPARQL query asynchronously.
    Args: query: str: A SPARQL query to be sent asynchronously.
    Returns: httpx.Response: A httpx.Response object
    """
    query_rq = async_client.build_request(
        "POST",
        url=settings.sparql_endpoint,
        headers={"Accept": mediatype},
        data={"query": query},
    )
    return await async_client.send(query_rq, stream=True)


async def send_queries(queries: List[str]):
    """Sends multiple SPARQL queries asynchronously.
    Args: queries: List[str]: A list of SPARQL queries to be sent asynchronously.
    Returns: List[httpx.Response]: A list of httpx.Response objects, one for each query
    """
    return await asyncio.gather(*[send_query(query) for query in queries])


async def query_to_graph(query: str):
    """
    Sends a SPARQL query asynchronously and parses the response into an RDFLib Graph.
    Args: query: str: A SPARQL query to be sent asynchronously.
    Returns: rdflib.Graph: An RDFLib Graph object
    """
    response = await send_query(query)
    g = Graph()
    await response.aread()
    return g.parse(data=response.text, format="turtle")


async def queries_to_graph(queries: List[str]):
    """
    Sends multiple SPARQL queries asynchronously and parses the responses into an RDFLib Graph.
    Args: queries: List[str]: A list of SPARQL queries to be sent asynchronously.
    Returns: rdflib.Graph: An RDFLib Graph object
    """
    graphs = await asyncio.gather(
        *[query_to_graph(query) for query in queries if query]
    )
    for g in graphs[1:]:
        graphs[0].__iadd__(g)
    return graphs[0]
