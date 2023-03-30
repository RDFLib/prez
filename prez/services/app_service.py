import logging
import time
from pathlib import Path

import httpx
from rdflib import URIRef, Literal, BNode, RDF, Graph

from prez.cache import (
    prez_system_graph,
    profiles_graph_cache,
    counts_graph,
    top_level_graph,
    prefix_graph
)
from prez.config import settings
from prez.reference_data.prez_ns import PREZ, ALTREXT
from prez.sparql.methods import sparql_construct
from prez.sparql.objects_listings import startup_count_objects
from prez.sparql.support_graphs import (
    generate_insert_context,
)

log = logging.getLogger(__name__)


async def healthcheck_sparql_endpoints():
    ENABLED_PREZS = settings.enabled_prezs
    log.info(f"Enabled Prezs: {', '.join(ENABLED_PREZS)}")
    if len(ENABLED_PREZS) > 0:
        for prez in ENABLED_PREZS:
            connected_to_prez_flavour = False
            log.info(
                f"Checking {prez} SPARQL endpoint {settings.sparql_creds[prez]['endpoint']} is online"
            )
            username = settings.sparql_creds[prez].get("username")
            password = settings.sparql_creds[prez].get("password")
            if username or password:
                auth = (username, password)
            else:
                auth = None
            while not connected_to_prez_flavour:
                try:
                    response = httpx.get(
                        settings.sparql_creds[prez]["endpoint"],
                        auth=auth,
                        params={"query": "ASK {}"},
                    )
                    response.raise_for_status()
                    if response.status_code == 200:
                        log.info(f"Successfully connected to {prez} SPARQL endpoint")
                        connected_to_prez_flavour = True
                except httpx.HTTPError as exc:
                    log.error(f"HTTP Exception for {exc.request.url} - {exc}")
                    log.error(
                        f"Failed to connect to {prez} endpoint {settings.sparql_creds[prez]}"
                    )
                    log.info("retrying in 3 seconds...")
                    time.sleep(3)
    else:
        raise ValueError(
            'No Prezs enabled - set one or more Prez SPARQL endpoint environment variables: ("SPACEPREZ_SPARQL_ENDPOINT",'
            '"VOCPREZ_SPARQL_ENDPOINT", and "CATPREZ_SPARQL_ENDPOINT")'
        )


async def count_objects():
    query = startup_count_objects()
    for prez in settings.enabled_prezs:
        results = await sparql_construct(query, prez)
        if results[0]:
            counts_graph.__add__(results[1])


async def populate_api_info():
    for prez in settings.enabled_prezs:
        bnode = BNode()
        prez_system_graph.add(
            (URIRef(settings.system_uri), PREZ.enabledPrezFlavour, bnode)
        )
        prez_system_graph.add((bnode, RDF.type, PREZ[prez]))
        # add links to prez subsystems
        prez_system_graph.add((bnode, PREZ.link, Literal(f"/{prez[0].lower()}")))

        # add links to search methods
        sys_prof = profiles_graph_cache.value(None, ALTREXT.constrainsClass, PREZ[prez])
        if sys_prof:
            search_methods = [
                sm
                for sm in profiles_graph_cache.objects(
                    sys_prof, PREZ.supportedSearchMethod
                )
            ]
            for method in search_methods:
                prez_system_graph.add((bnode, PREZ.availableSearchMethod, method))

    prez_system_graph.add(
        (URIRef(settings.system_uri), PREZ.version, Literal(settings.prez_version))
    )
    log.info(f"Populated API info")


async def add_prefixes_to_prefix_graph():
    """
    Adds prefixes to the prefix graph
    """
    for f in (Path(__file__).parent.parent / "reference_data/prefixes").glob("*.ttl"):
        g = Graph().parse(f, format="turtle")
        for subject_objects in g.subject_objects(
                predicate=URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix")):
            prefix_graph.bind(str(subject_objects[1]), subject_objects[0])
            log.info(f"Prefix \"{str(subject_objects[1])}\" bound to namespace {str(subject_objects[0])} from file "
                     f"\"{f.name}\"")
    log.info("Prefixes from local files added to prefix graph")

async def generate_support_graphs():
    """
    Generates the support graphs needed for the Prez API, populating the local "top_level_graph" graph, stored in
    prez.cache.
    """
    for prez in settings.enabled_prezs:
        log.info(f"Adding Top Level Classes for {prez} to top level graph")
        insert_context = generate_insert_context(settings, prez)
        results = await sparql_construct(insert_context, prez)
        if results[0]:
            top_level_graph.__iadd__(results[1])
            log.info(f"Completed generating Support Graphs for {prez}")

    # profiles
    insert_context = generate_insert_context(settings, "Profiles")
    results = profiles_graph_cache.query(insert_context)
    top_level_graph.__iadd__(results.graph)
    log.info(f"Completed generating Support Graphs for Profiles")
