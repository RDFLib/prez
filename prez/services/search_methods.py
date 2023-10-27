import logging
from pathlib import Path
from string import Template

from rdflib import Graph, RDF, DCTERMS, Literal, RDFS

from prez.cache import search_methods
from prez.models import SearchMethod
from prez.reference_data.prez_ns import PREZ

log = logging.getLogger(__name__)


async def get_all_search_methods(repo):
    await get_local_search_methods()
    await get_remote_search_methods(repo)


async def get_remote_search_methods(repo):
    remote_search_methods_query = f"""
    PREFIX prez: <{PREZ}>
    CONSTRUCT {{?s ?p ?o}}
    WHERE {{ ?s a prez:SearchMethod ;
               ?p ?o . }}
    """
    graph, _ = await repo.send_queries([remote_search_methods_query], [])
    if len(graph) > 1:
        await generate_search_methods(graph)
        log.info(f"Remote search methods found and added.")
    else:
        log.info("No remote search methods found.")


async def get_local_search_methods():
    for f in (Path(__file__).parent.parent / "reference_data/search_methods").glob(
        "*.ttl"
    ):
        g = Graph().parse(f, format="ttl")
        await generate_search_methods(g)


async def generate_search_methods(g):
    uri = g.value(None, RDF.type, PREZ.SearchMethod)
    identifier = g.value(uri, DCTERMS.identifier, None)
    title: Literal = g.value(uri, RDFS.label, None)
    template_query = Template(g.value(uri, RDF.value, None))
    sm = SearchMethod(
        uri=uri, identifier=identifier, title=title, template_query=template_query
    )
    search_methods.update({identifier: sm})
