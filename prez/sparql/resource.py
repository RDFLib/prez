from rdflib import Graph

from prez.sparql.methods import rdf_query_to_graph


async def get_resource(iri: str) -> Graph:
    query = f"""DESCRIBE <{iri}>"""
    return await rdf_query_to_graph(query)
