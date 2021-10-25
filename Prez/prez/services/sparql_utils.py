from httpx import AsyncClient, Response
from rdflib import Graph

from config import *


async def sparql_query(query: str):
    async with AsyncClient() as client:
        response: Response = await client.post(
            SPARQL_ENDPOINT,
            data=query,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/sparql-query",
            },
            auth=(SPARQL_USERNAME, SPARQL_PASSWORD),
        )
    if 200 <= response.status_code < 300:
        return True, response.json()["results"]["bindings"]
    else:
        return False, response.status_code, response.text


async def sparql_construct(query: str):
    async with AsyncClient() as client:
        response: Response = await client.post(
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
