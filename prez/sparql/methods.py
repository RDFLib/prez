import logging
from functools import lru_cache
from typing import Dict, List, Tuple, Union

from async_lru import alru_cache
from httpx import Client, HTTPError, HTTPStatusError
from httpx import Response as httpxResponse
from rdflib import Graph
from starlette.responses import PlainTextResponse

from prez.config import settings
from prez.services.triplestore_client import sparql_clients

log = logging.getLogger(__name__)

TIMEOUT = 30.0


def sparql_query_non_async(query: str, prez: str) -> Tuple[bool, Union[List, Dict]]:
    """Executes a SPARQL SELECT query for a single SPARQL endpoint"""

    with Client() as client:
        response: httpxResponse = client.post(
            settings.sparql_creds[prez]["endpoint"],
            data=query,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/sparql-query",
            },
            auth=(
                settings.sparql_creds[prez].get("username", ""),
                settings.sparql_creds[prez].get("password", ""),
            ),
            timeout=TIMEOUT,
        )
    if 200 <= response.status_code < 300:
        return True, response.json()["results"]["bindings"]
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }


async def sparql_query(query: str, prez: str) -> Tuple[bool, Union[List, Dict]]:
    """Executes a SPARQL SELECT query for a single SPARQL endpoint"""
    be_endpoint = settings.sparql_creds[prez]["endpoint"]
    fe_endpoint = f"{settings.protocol}://{settings.host}:{settings.port}/{prez[0].lower()}/sparql"
    logging.info(msg=f"Executing query {query} against {be_endpoint}")
    try:
        response: httpxResponse = await sparql_clients[prez].post(
            url="",
            data=query,
            headers={
                "Accept": "text/turtle, application/json",
                "Content-Type": "application/sparql-query",
            },
            auth=(
                settings.sparql_creds[prez].get("username", ""),
                settings.sparql_creds[prez].get("password", ""),
            ),
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except HTTPStatusError:
        log.error(f"HTTPStatusError text: {response.text}")
        return PlainTextResponse(
            content=response.text, status_code=response.status_code
        )
    if 200 <= response.status_code < 300:
        response_mt = response.headers["content-type"]
        if response_mt.startswith("application/json"):
            response = response.json()
            response["head"]["link"] = query
            return fe_endpoint, response_mt, response
        elif response_mt.startswith("text/turtle"):
            return (
                fe_endpoint,
                response_mt,
                Graph(bind_namespaces="rdflib").parse(data=response.text),
            )
    else:
        return "text/plain", {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }


@alru_cache(maxsize=128)
async def sparql_construct(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    if prez == "GenericPrez":
        from prez.cache import profiles_graph_cache

        results = profiles_graph_cache.query(query)
        return True, results
    if not query:
        return False, None
    try:

        response: httpxResponse = await sparql_clients[prez].post(
            url="",
            data=query,
            auth=(
                settings.sparql_creds[prez].get("username", ""),
                settings.sparql_creds[prez].get("password", ""),
            ),
            headers={
                "Accept": "text/turtle",
                "Content-Type": "application/sparql-query",
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except HTTPError as e:
        {
            "code": e.response.status_code,
            "message": e.response.text,
            "prez": prez,
        }
    if 200 <= response.status_code < 300:
        return True, Graph(bind_namespaces="rdflib").parse(data=response.text)
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }


async def sparql_update(request, prez):
    headers = {
        "Authorization": request.headers.get("Authorization"),
        "Content-Type": request.headers.get("Content-Type"),
    }
    data = await request.body()

    try:
        response: httpxResponse = await sparql_clients[prez].post(
            settings.sparql_creds[prez]["update"],
            data=data,
            headers=headers,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except HTTPError:
        raise
    if 200 <= response.status_code < 300:
        return response.text
    else:
        raise Exception(
            {
                "code": response.status_code,
                "message": response.text,
                "prez": prez,
            }
        )


@alru_cache(maxsize=128)
async def sparql_ask(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    if not query:
        return False, None
    try:
        response: httpxResponse = await sparql_clients[prez].post(
            settings.sparql_creds[prez]["endpoint"],
            data={"query": query},
            auth=(
                settings.sparql_creds[prez].get("username", ""),
                settings.sparql_creds[prez].get("password", ""),
            ),
            headers={
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except HTTPError as e:
        {
            "code": e.response.status_code,
            "message": e.response.text,
            "prez": prez,
        }
    if 200 <= response.status_code < 300:
        return True, response.json()["boolean"]
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }


@lru_cache(maxsize=128)
def sparql_ask_non_async(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    with Client() as client:
        response: httpxResponse = client.post(
            settings.sparql_creds[prez]["endpoint"],
            data={"query": query},
            headers={
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept-Encoding": "gzip, deflate",
            },
            auth=(
                settings.sparql_creds[prez].get("username", ""),
                settings.sparql_creds[prez].get("password", ""),
            ),
            timeout=TIMEOUT,
        )
    if 200 <= response.status_code < 300:
        return True, response.json()["boolean"]
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }


@lru_cache(maxsize=128)
def sparql_construct_non_async(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""

    with Client() as client:
        response: httpxResponse = client.post(
            settings.sparql_creds[prez]["endpoint"],
            data=query,
            headers={
                "Accept": "text/turtle",
                "Content-Type": "application/sparql-query",
            },
            auth=(
                settings.sparql_creds[prez].get("username", ""),
                settings.sparql_creds[prez].get("password", ""),
            ),
            timeout=TIMEOUT,
        )
    if 200 <= response.status_code < 300:
        return True, Graph(bind_namespaces="rdflib").parse(data=response.text)
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }
