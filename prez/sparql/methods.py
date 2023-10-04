import asyncio
import logging
from typing import Dict, Tuple, Union, Any
from typing import List

import httpx
from httpx import Client, AsyncClient, HTTPError
from httpx import Response as httpxResponse
from rdflib import Namespace, Graph, URIRef
from starlette.requests import Request
from async_lru import alru_cache
from prez.config import settings

PREZ = Namespace("https://prez.dev/")

async_client = AsyncClient(
    auth=(settings.sparql_username, settings.sparql_password)
    if settings.sparql_username
    else None,
    timeout=settings.sparql_timeout,
)

client = Client(
    auth=(settings.sparql_username, settings.sparql_password)
    if settings.sparql_username
    else None,
    timeout=settings.sparql_timeout,
)

log = logging.getLogger(__name__)


def sparql_query_non_async(query: str) -> Tuple[bool, Union[List, Dict]]:
    """Executes a SPARQL SELECT query for a single SPARQL endpoint"""
    response: httpxResponse = client.post(
        settings.sparql_endpoint,
        data=query,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/sparql-query",
        },
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


# @alru_cache(maxsize=1000)
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
    response = await async_client.send(query_rq, stream=True)
    return response


async def rdf_query_to_graph(query: str) -> Graph:
    """
    Sends a SPARQL query asynchronously and parses the response into an RDFLib Graph.
    Args: query: str: A SPARQL query to be sent asynchronously.
    Returns: rdflib.Graph: An RDFLib Graph object
    """
    response = await send_query(query)
    g = Graph()
    await response.aread()
    return g.parse(data=response.text, format="turtle")


async def send_queries(
    rdf_queries: List[str], tabular_queries: List[Tuple[URIRef, str]] = None
) -> Tuple[Graph, List[Any]]:
    """
    Sends multiple SPARQL queries asynchronously and parses the responses into an RDFLib Graph for RDF queries
    and a table format for table queries.

    Args:
        rdf_queries: List[str]: A list of SPARQL queries for RDF graphs to be sent asynchronously.
        tabular_queries: List[str]: A list of SPARQL queries for tables to be sent asynchronously.

    Returns:
        Tuple[rdflib.Graph, List[Any]]: An RDFLib Graph object for RDF queries and a list of tables for table queries.
    """
    if tabular_queries is None:
        tabular_queries = []
    results = await asyncio.gather(
        *[rdf_query_to_graph(query) for query in rdf_queries if query],
        *[
            tabular_query_to_table(query, context)
            for context, query in tabular_queries
            if query
        ]
    )
    g = Graph()
    tabular_results = []
    for result in results:
        if isinstance(result, Graph):
            g += result
        else:
            tabular_results.append(result)
    return g, tabular_results


async def tabular_query_to_table(query: str, context: URIRef = None):
    """
    Sends a SPARQL query asynchronously and parses the response into a table format.
    The optional context parameter allows an identifier to be supplied with the query, such that multiple results can be
    distinguished from each other.
    """
    response = await send_query(query, "application/sparql-results+json")
    await response.aread()
    return context, response.json()["results"]["bindings"]
