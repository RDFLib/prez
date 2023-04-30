import logging
from pathlib import Path
from string import Template

from rdflib import Graph, RDF, DCTERMS, Literal, RDFS

from prez.cache import search_methods
from prez.config import settings
from prez.models import SearchMethod
from prez.reference_data.prez_ns import PREZ
from prez.sparql.methods import sparql_construct

log = logging.getLogger(__name__)


async def get_all_search_methods():
    await get_local_search_methods()
    await get_remote_search_methods()


async def get_remote_search_methods():
    remote_search_methods_query = f"""
    PREFIX prez: <{PREZ}>
    CONSTRUCT {{?s ?p ?o}}
    WHERE {{ GRAPH prez:systemGraph {{ ?s a prez:SearchMethod ;
               ?p ?o . }} }}
    """
    any_remote_search_methods = False
    for p in settings.enabled_prezs:
        r = await sparql_construct(remote_search_methods_query, p)
        if r[0] and r[1]:
            any_remote_search_methods = True
            await generate_search_methods(r[1])
            log.info(f"Remote search methods found and added for {p}")
    if not any_remote_search_methods:
        log.info("No remote search methods found")


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
