import logging

from rdflib import Namespace, URIRef, DCTERMS, RDF, XSD, SKOS

from prez.cache import prez_system_graph
from prez.services.sparql_new import generate_insert_context, ask_system_graph
from prez.services.sparql_utils import sparql_construct, sparql_update, sparql_ask

log = logging.getLogger(__name__)


PREZ = Namespace("https://prez.dev/")


async def populate_api_info(settings):
    for prez in settings.enabled_prezs:
        prez_system_graph.add(
            (URIRef(settings.system_uri), PREZ.enabledPrezFlavour, PREZ[prez])
        )
        log.debug(f"Populated API info for {prez}")


async def generate_context(settings):
    """
    Generates the contextual graphs needed for the Prez API.
    Although context is placed in specific graphs, prez itself is graph agnostic: it is assumed backend triplestores
    have a default union graph that covers all data intended to be delivered by the API.
    """
    for prez in settings.enabled_prezs:
        # if running on startup, there may already be a system graph, in which case we don't need to generate it
        # if the user wishes to regenerate the system graph, they can do so by using the /regenerate-context endpoint
        ask = ask_system_graph(prez)
        sys_g_exists = await sparql_ask(ask, prez)
        if sys_g_exists[0] and sys_g_exists[1]:
            log.info(
                f"System graph for {prez} already exists, skipping generation of context"
            )
        # select instances which do not have context graphs, log these instances
        elif settings.generate_context:
            insert_context = generate_insert_context(settings, prez)
            response = await sparql_update(insert_context, prez)
            log.info(f"Generated context for {prez}")
            if not response[0]:
                raise Exception(response[1])
