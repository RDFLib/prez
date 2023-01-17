import logging

from rdflib import Namespace, URIRef, Literal

from prez.cache import prez_system_graph, profiles_graph_cache
from prez.services.sparql_queries import generate_insert_context, ask_system_graph
from prez.services.sparql_utils import sparql_update, sparql_ask

log = logging.getLogger(__name__)


PREZ = Namespace("https://prez.dev/")


async def populate_api_info(settings):
    for prez in settings.enabled_prezs:
        prez_system_graph.add(
            (URIRef(settings.system_uri), PREZ.enabledPrezFlavour, PREZ[prez])
        )
        # add links to prez subsystems
        prez_system_graph.add(
            (URIRef(settings.system_uri), PREZ.link, Literal(f"/{prez[0].lower()}"))
        )
        # add prez version
        prez_system_graph.add(
            (URIRef(settings.system_uri), PREZ.version, Literal(settings.prez_version))
        )

        log.debug(f"Populated API info for {prez}")


async def generate_support_graphs(settings):
    """
    Generates the support graphs needed for the Prez API.
    Although supporting triples are placed in specific graphs, Prez itself is graph agnostic: it is assumed backend
    triplestores have a default union graph that covers all data intended to be delivered by the API.
    """
    for prez in settings.enabled_prezs:
        # if running on startup, there may already be a system graph, in which case we don't need to generate it
        # if the user wishes to regenerate the system graph, they can do so by using the /regenerate-context endpoint
        ask = ask_system_graph(prez)
        sys_g_exists = await sparql_ask(ask, prez)
        if sys_g_exists[0] and sys_g_exists[1]:
            log.info(
                f"System graph for {prez} already exists, skipping generation of support graphs"
            )
        # select instances which do not have support graphs, log these instances
        elif settings.generate_support_graphs:
            log.info(f"Generating Support Graphs for {prez}")
            insert_context = generate_insert_context(settings, prez)
            await sparql_update(insert_context, prez)
            log.info(f"Completed generating Support Graphs for {prez}")


async def generate_profiles_support_graph(settings):
    """
    Generates a support graph for the prez profiles
    """
    insert_context = generate_insert_context(settings, "Profiles")
    profiles_graph_cache.update(insert_context)
    log.info(f"Completed generating Support Graphs for Profiles")
