from rdflib import Graph

from prez.sparql.methods import Repo


async def get_resource(iri: str, repo: Repo) -> Graph:
    query = f"""DESCRIBE <{iri}>"""
    graph, _ = await repo.send_queries([query], [])
    return graph
