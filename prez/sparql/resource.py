from rdflib import Graph

from prez.sparql.methods import query_to_graph


async def get_resource(iri: str) -> Graph:
    query = f"""DESCRIBE <{iri}>"""
    return await query_to_graph(query)
