from httpx import AsyncClient
from httpx import Response as httpxResponse
from rdflib import Graph

from config import *


async def sparql_query(query: str, accept: str = "application/json"):
    async with AsyncClient() as client:
        response: httpxResponse = await client.post(
            SPARQL_ENDPOINT,
            data=query,
            headers={
                "Accept": f"{accept}",
                "Content-Type": "application/sparql-query",
            },
            auth=(SPARQL_USERNAME, SPARQL_PASSWORD),
        )
    if 200 <= response.status_code < 300:
        if accept == "application/json":
            return True, response.json()["results"]["bindings"]
        else:
            return True, response.text
    else:
        return False, response.status_code, response.text


async def sparql_construct(query: str):
    """Returns an rdflib Graph from a CONSTRUCT query"""
    async with AsyncClient() as client:
        response: httpxResponse = await client.post(
            SPARQL_ENDPOINT,
            data=query,
            headers={
                "Accept": "text/turtle",
                "Content-Type": "application/sparql-query",
            },
            auth=(SPARQL_USERNAME, SPARQL_PASSWORD),
        )
    if 200 <= response.status_code < 300:
        return True, Graph().parse(data=response.text, format="turtle")
    else:
        return False, response.status_code, response.text
