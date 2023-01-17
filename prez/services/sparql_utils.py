import asyncio
import logging
import os
from functools import lru_cache
from typing import Dict, List, Tuple, Union

from async_lru import alru_cache
from connegp import RDF_MEDIATYPES
from httpx import AsyncClient, Client, HTTPError
from httpx import Response as httpxResponse
from rdflib import Graph, RDF

log = logging.getLogger(__name__)

TIMEOUT = 30.0


@lru_cache(maxsize=128)
def sparql_query_non_async(query: str, prez: str) -> Tuple[bool, Union[List, Dict]]:
    """Executes a SPARQL SELECT query for a single SPARQL endpoint"""
    from prez.app import settings

    with Client() as client:
        response: httpxResponse = client.post(
            settings.sparql_creds[prez]["endpoint"],
            data=query,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/sparql-query",
            },
            # auth=(settings.sparql_creds[prez]["username"], settings.sparql_creds[prez]["password"]),
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
    from app import settings

    logging.info(
        msg=f"Executing query {query} against {settings.sparql_creds[prez]['endpoint']}"
    )

    async with AsyncClient() as client:
        response: httpxResponse = await client.post(
            settings.sparql_creds[prez]["endpoint"],
            data=query,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/sparql-query",
            },
            auth=(
                settings.sparql_creds[prez]["username"],
                settings.sparql_creds[prez]["password"],
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


# async def sparql_construct(query: str, prez: str):
#     """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
#     from prez.app import settings
#
#     if not query:
#         return False, None
#     async with AsyncClient() as client:
#         response: httpxResponse = await client.post(
#             url=settings.sparql_creds[prez]["endpoint"],
#             data=query,
#             headers={
#                 "Accept": "text/turtle",
#                 "Content-Type": "application/sparql-query",
#             },
#             # auth=(settings.sparql_creds[prez]["username"], settings.sparql_creds[prez]["password"]),
#             timeout=TIMEOUT,
#         )
#     if 200 <= response.status_code < 300:
#         return True, Graph().parse(data=response.text)


async def sparql_construct(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    from prez.app import settings

    if prez == "GenericPrez":
        from cache import profiles_graph_cache

        results = profiles_graph_cache.query(query)
        return True, results
    if not query:
        return False, None
    try:
        async with AsyncClient() as client:
            response: httpxResponse = await client.post(
                settings.sparql_creds[prez]["endpoint"],
                data=query,
                headers={
                    "Accept": "text/turtle",
                    "Content-Type": "application/sparql-query",
                    "Accept-Encoding": "gzip, deflate",
                },
                # auth=(settings.sparql_creds[prez]["username"], settings.sparql_creds[prez]["password"]),
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


async def sparql_update(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    from prez.app import settings

    if not query:
        return False, None
    try:
        async with AsyncClient() as client:
            response: httpxResponse = await client.post(
                settings.sparql_creds[prez]["update"],
                data=query,
                headers={
                    "Content-Type": "application/sparql-update",
                },
                # auth=(settings.sparql_creds[prez]["username"], settings.sparql_creds[prez]["password"]),
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


async def sparql_ask(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    from prez.app import settings

    if not query:
        return False, None
    try:
        async with AsyncClient() as client:
            response: httpxResponse = await client.post(
                settings.sparql_creds[prez]["endpoint"],
                data={"query": query},
                headers={
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept-Encoding": "gzip, deflate",
                },
                # auth=(settings.sparql_creds[prez]["username"], settings.sparql_creds[prez]["password"]),
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


def sparql_construct_non_async(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    from prez.app import settings

    with Client() as client:
        response: httpxResponse = client.post(
            settings.sparql_creds[prez]["endpoint"],
            data=query,
            headers={
                "Accept": "text/turtle",
                "Content-Type": "application/sparql-query",
            },
            # auth=(creds[prez]["username"], creds[prez]["password"]),
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
