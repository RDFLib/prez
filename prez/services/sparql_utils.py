from typing import Dict, List, Tuple, Union

from httpx import AsyncClient, Client
from httpx import Response as httpxResponse
import asyncio
from connegp import RDF_MEDIATYPES

from prez.config import *

TIMEOUT = 30.0

get_all_prop_obj_info = """
OPTIONAL {
    ?p1 rdfs:label|dcterms:title ?p1Label .
    FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
}
OPTIONAL {
    ?p1 dcterms:description ?p1def .
    FILTER(lang(?p1def) = "" || lang(?p1def) = "en")
}
OPTIONAL {
    ?p1 dcterms:provenance ?p1expl .
    FILTER(lang(?p1expl) = "" || lang(?p1expl) = "en")
}
OPTIONAL {
    ?o1 rdfs:label|dcterms:title ?o1Label .
    FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
}
OPTIONAL {
    ?o1 dcterms:description ?o1def .
    FILTER(lang(?o1def) = "" || lang(?o1def) = "en")
}
"""

get_all_bnode_prop_obj_info = """
OPTIONAL {
    ?o1 ?p2 ?o2 .
    FILTER(ISBLANK(?o1))

    OPTIONAL {
        ?p2 rdfs:label|dcterms:title ?p2Label .
        FILTER(lang(?p2Label) = "" || lang(?p2Label) = "en")
    }
    OPTIONAL {
        ?p2 dcterms:description ?p2def .
        FILTER(lang(?p2def) = "" || lang(?p2def) = "en")
    }
    OPTIONAL {
        ?p2 dcterms:provenance ?p2expl .
        FILTER(lang(?p2expl) = "" || lang(?p2expl) = "en")
    }
    OPTIONAL {
        ?o2 rdfs:label|dcterms:title ?o2Label .
        FILTER(lang(?o2Label) = "" || lang(?o2Label) = "en")
    }
    OPTIONAL {
        ?o2 dcterms:description ?o2def .
        FILTER(lang(?o2def) = "" || lang(?o2def) = "en")
    }
}
"""

construct_all_prop_obj_info = """
?p1 rdfs:label ?p1Label ;
    dcterms:description ?p1def ;
    dcterms:provenance ?p1expl .
?o1 rdfs:label ?o1Label ;
    dcterms:description ?o1def .
"""

construct_all_bnode_prop_obj_info = """
?o1 ?p2 ?o2 .
?p2 rdfs:label ?p2Label ;
    dcterms:description ?p2def ;
    dcterms:provenance ?p2expl .
?o2 rdfs:label ?o2Label ;
    dcterms:description ?o2def .
"""


def sparql_query_non_async(query: str, prez: str) -> Tuple[bool, Union[List, Dict]]:
    """Executes a SPARQL SELECT query for a single SPARQL endpoint"""
    creds = {"endpoint": "", "username": "", "password": ""}
    if prez == "CatPrez":
        creds["endpoint"] = CATPREZ_SPARQL_ENDPOINT
        creds["username"] = CATPREZ_SPARQL_USERNAME
        creds["password"] = CATPREZ_SPARQL_PASSWORD
    elif prez == "VocPrez":
        creds["endpoint"] = VOCPREZ_SPARQL_ENDPOINT
        creds["username"] = VOCPREZ_SPARQL_USERNAME
        creds["password"] = VOCPREZ_SPARQL_PASSWORD
    elif prez == "SpacePrez":
        creds["endpoint"] = SPACEPREZ_SPARQL_ENDPOINT
        creds["username"] = SPACEPREZ_SPARQL_USERNAME
        creds["password"] = SPACEPREZ_SPARQL_PASSWORD
    else:
        raise Exception(
            "Invalid prez specified in sparql_query call. Available options are: 'VocPrez', 'SpacePrez'."
        )
    with Client() as client:
        response: httpxResponse = client.post(
            creds["endpoint"],
            data=query,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/sparql-query",
            },
            auth=(creds["username"], creds["password"]),
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
    creds = {"endpoint": "", "username": "", "password": ""}
    if prez == "CatPrez":
        creds["endpoint"] = CATPREZ_SPARQL_ENDPOINT
        creds["username"] = CATPREZ_SPARQL_USERNAME
        creds["password"] = CATPREZ_SPARQL_PASSWORD
    elif prez == "VocPrez":
        creds["endpoint"] = VOCPREZ_SPARQL_ENDPOINT
        creds["username"] = VOCPREZ_SPARQL_USERNAME
        creds["password"] = VOCPREZ_SPARQL_PASSWORD
    elif prez == "SpacePrez":
        creds["endpoint"] = SPACEPREZ_SPARQL_ENDPOINT
        creds["username"] = SPACEPREZ_SPARQL_USERNAME
        creds["password"] = SPACEPREZ_SPARQL_PASSWORD
    else:
        raise Exception(
            "Invalid prez specified in sparql_query call. Available options are: 'CatPrez', 'VocPrez', 'SpacePrez'."
        )
    async with AsyncClient() as client:
        response: httpxResponse = await client.post(
            creds["endpoint"],
            data=query,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/sparql-query",
            },
            auth=(creds["username"], creds["password"]),
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


def sparql_query_multiple_non_async(
    query: str, prezs: List[str] = ENABLED_PREZS
) -> Tuple[List, List]:
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


async def sparql_query_multiple(
    query: str, prezs: List[str] = ENABLED_PREZS
) -> Tuple[List, List]:
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
    creds = {"endpoint": "", "username": "", "password": ""}
    if prez == "CatPrez":
        creds["endpoint"] = CATPREZ_SPARQL_ENDPOINT
        creds["username"] = CATPREZ_SPARQL_USERNAME
        creds["password"] = CATPREZ_SPARQL_PASSWORD
    elif prez == "VocPrez":
        creds["endpoint"] = VOCPREZ_SPARQL_ENDPOINT
        creds["username"] = VOCPREZ_SPARQL_USERNAME
        creds["password"] = VOCPREZ_SPARQL_PASSWORD
    elif prez == "SpacePrez":
        creds["endpoint"] = SPACEPREZ_SPARQL_ENDPOINT
        creds["username"] = SPACEPREZ_SPARQL_USERNAME
        creds["password"] = SPACEPREZ_SPARQL_PASSWORD
    else:
        raise Exception(
            "Invalid prez specified in sparql_query call. Available options are: 'CatPrez', 'VocPrez', 'SpacePrez'."
        )
    async with AsyncClient() as client:
        response: httpxResponse = await client.post(
            creds["endpoint"],
            data=query,
            headers={
                "Accept": "text/turtle",
                "Content-Type": "application/sparql-query",
            },
            auth=(creds["username"], creds["password"]),
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
    creds = {"endpoint": "", "username": "", "password": ""}
    if prez == "CatPrez":
        creds["endpoint"] = CATPREZ_SPARQL_ENDPOINT
        creds["username"] = CATPREZ_SPARQL_USERNAME
        creds["password"] = CATPREZ_SPARQL_PASSWORD
    elif prez == "VocPrez":
        creds["endpoint"] = VOCPREZ_SPARQL_ENDPOINT
        creds["username"] = VOCPREZ_SPARQL_USERNAME
        creds["password"] = VOCPREZ_SPARQL_PASSWORD
    elif prez == "SpacePrez":
        creds["endpoint"] = SPACEPREZ_SPARQL_ENDPOINT
        creds["username"] = SPACEPREZ_SPARQL_USERNAME
        creds["password"] = SPACEPREZ_SPARQL_PASSWORD
    else:
        raise Exception(
            "Invalid prez specified in sparql_query call. Available options are: 'CatPrez', 'VocPrez', 'SpacePrez'."
        )
    with Client() as client:
        response: httpxResponse = client.post(
            creds["endpoint"],
            data=query,
            headers={
                "Accept": "text/turtle",
                "Content-Type": "application/sparql-query",
            },
            auth=(creds["username"], creds["password"]),
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
    creds = {"endpoint": "", "username": "", "password": ""}
    if prez == "CatPrez":
        creds["endpoint"] = CATPREZ_SPARQL_ENDPOINT
        creds["username"] = CATPREZ_SPARQL_USERNAME
        creds["password"] = CATPREZ_SPARQL_PASSWORD
    elif prez == "VocPrez":
        creds["endpoint"] = VOCPREZ_SPARQL_ENDPOINT
        creds["username"] = VOCPREZ_SPARQL_USERNAME
        creds["password"] = VOCPREZ_SPARQL_PASSWORD
    elif prez == "SpacePrez":
        creds["endpoint"] = SPACEPREZ_SPARQL_ENDPOINT
        creds["username"] = SPACEPREZ_SPARQL_USERNAME
        creds["password"] = SPACEPREZ_SPARQL_PASSWORD
    else:
        raise Exception(
            "Invalid Prez specified in sparql_query call. Available options are: 'VocPrez', 'SpacePrez'."
        )
    async with AsyncClient() as client:
        response: httpxResponse = await client.post(
            creds["endpoint"],
            data=query,
            headers={
                "Accept": f"{accept}",
                "Content-Type": "application/sparql-query",
            },
            auth=(creds["username"], creds["password"]),
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
                    succeeded_results["results"]["bindings"] += result[1]["results"]["bindings"]
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
