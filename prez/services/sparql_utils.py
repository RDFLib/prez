import asyncio
import os
from typing import Dict, List, Tuple, Union

from connegp import RDF_MEDIATYPES
from httpx import AsyncClient, Client
from httpx import Response as httpxResponse
from rdflib import Graph, RDF

TIMEOUT = 30.0


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
        response: httpxResponse = await client.post(
            settings.sparql_creds[prez]["endpoint"],
            data=query,
            headers={
                "Accept": "text/turtle",
                "Content-Type": "application/sparql-query",
            },
            # auth=(settings.sparql_creds[prez]["username"], settings.sparql_creds[prez]["password"]),
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


def sparql_construct_non_async(query: str, prez: str):
    """Returns an rdflib Graph from a CONSTRUCT query for a single SPARQL endpoint"""
    from app import settings

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


async def sparql_endpoint_query(
    query: str, prez: str, accept: str
) -> Tuple[bool, Union[Dict, str]]:
    """Queries a SPARQL query on a single endpoint for some Accept mediatype"""
    async with AsyncClient() as client:
        response: httpxResponse = await client.post(
            creds[prez]["endpoint"],
            data=query,
            headers={
                "Accept": f"{accept}",
                "Content-Type": "application/sparql-query",
            },
            auth=(creds[prez]["username"], creds[prez]["password"]),
            timeout=TIMEOUT,
        )
    if 200 <= response.status_code < 300:
        if accept in ["application/sparql-results+json", "application/json"]:
            return True, response.json()
        else:
            return True, response.text
    else:
        return False, {
            "code": response.status_code,
            "message": response.text,
            "prez": prez,
        }


async def sparql_endpoint_query_multiple(
    query: str, accept: str = "application/sparql-results+json"
) -> Tuple[Union[str, Dict], List]:
    """Queries a SPARQL query on multiple endpoints for some Accept mediatype"""
    results = await asyncio.gather(
        *[sparql_endpoint_query(query, prez, accept) for prez in ENABLED_PREZS]
    )
    succeeded_results = Graph() if accept in RDF_MEDIATYPES else {}
    failed_results = []
    for i, result in enumerate(results):
        if result[0]:
            if accept in RDF_MEDIATYPES:
                succeeded_results += Graph().parse(data=result[1], format=accept)
            elif accept in ["application/sparql-results+json", "application/json"]:
                # JSON for now (need to cater for XML, CSV & TSV)
                if len(succeeded_results.keys()) == 0:
                    succeeded_results = result[1]
                else:
                    succeeded_results["results"]["bindings"] += result[1]["results"][
                        "bindings"
                    ]
            else:  # XML
                succeeded_results[i] = result[1]
        else:
            failed_results += result[1]
    if accept in RDF_MEDIATYPES:
        return succeeded_results.serialize(format=accept), failed_results
    elif accept in ["application/sparql-results+json", "application/json"]:
        return succeeded_results, failed_results
    else:  # XML
        return succeeded_results[0], failed_results


def rdf_list_to_python_list(g: Graph, sub_pred: tuple) -> List:
    """
    Converts an RDF list to a Python list
    Parameters:
    g: and RDFLib Graph object containing the list to be converted to a python list
    sub_pred: the subject and predicate which uniqule identify the triple beginning the RDF list in the graph
    """
    python_list = []
    bn = g.value(*sub_pred)
    if bn:

        def inner_func(bn):
            inner_first = g.value(subject=bn, predicate=RDF.first)
            rest = g.value(subject=bn, predicate=RDF.rest)
            return inner_first, rest

        while bn != RDF.nil:
            first, bn = inner_func(bn)
            python_list.append(first)
    return python_list


def populate_sparql_creds():
    sparql_creds = {
        "CatPrez": {},
        "VocPrez": {},
        "SpacePrez": {},
    }
    ENABLED_PREZS = os.getenv("ENABLED_PREZS").split("|")
    for prez in ENABLED_PREZS:
        for attr in ["endpoint", "username", "password"]:
            key = f"{prez.upper()}_SPARQL_{attr.upper()}"
            value = os.getenv(key)
            if value:
                sparql_creds[prez][attr] = value
    return sparql_creds
