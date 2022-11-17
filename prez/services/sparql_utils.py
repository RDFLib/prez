import asyncio
import os
from functools import lru_cache
from typing import Dict, List, Tuple, Union

from async_lru import alru_cache
from connegp import RDF_MEDIATYPES
from httpx import AsyncClient, Client, HTTPError
from httpx import Response as httpxResponse
from rdflib import Graph, RDF


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


def sparql_query_multiple_non_async(query: str, prezs: List[str]) -> Tuple[List, List]:
    """Executes a SPARQL SELECT query for (potentially) multiple SPARQL endpoints

    If prezs arg is omitted, queries all available SPARQL endpoints.

    Returns a tuple of two lists: (succeeded_results, failed_results)

    The config variable ALLOW_PARTIAL_RESULTS should be used for checking if you should proceed if failed_results is not empty
    """
    succeeded_results = []
    failed_results = []
    for prez in prezs:
        result = sparql_query_non_async(query, prez)
        if result[0]:
            succeeded_results += result[1]
        else:
            failed_results += result[1]
    return succeeded_results, failed_results


async def sparql_query_multiple(query: str, prezs: List[str]) -> Tuple[List, List]:
    """Executes a SPARQL SELECT query for (potentially) multiple SPARQL endpoints

    If prezs arg is omitted, queries all available SPARQL endpoints.

    Returns a tuple of two lists: (succeeded_results, failed_results)

    The config variable ALLOW_PARTIAL_RESULTS should be used for checking if you should proceed if failed_results is not empty
    """
    results = await asyncio.gather(*[sparql_query(query, prez) for prez in prezs])
    succeeded_results = []
    failed_results = []
    for result in results:
        if result[0]:
            succeeded_results += result[1]
        else:
            failed_results += result[1]
    return succeeded_results, failed_results


async def sparql_construct(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    from prez.app import settings

    if not query:
        return False, None
    async with AsyncClient() as client:
        try:
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
        except HTTPError:
            raise
            #     "code": e.response.status_code,
            #     "message": e.response.text,
            #     "prez": prez,
            # }
    if 200 <= response.status_code < 300:
        return True, Graph().parse(data=response.text)
    else:
        raise HTTPError(response=response)
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
        return True, Graph().parse(data=response.text)
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }
