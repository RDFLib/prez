from rdflib import Graph

from prez.sparql.methods import Repo


async def get_resource(iri: str, query_sender: Repo) -> Graph:
    query = f"""DESCRIBE <{iri}>"""
    graph, _ = await query_sender.send_queries([query], [])
    return graph
