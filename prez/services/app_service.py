import logging
import time
from pathlib import Path

import httpx
from rdflib import URIRef, Literal, BNode, RDF, Graph

from prez.cache import (
    prez_system_graph,
    profiles_graph_cache,
    counts_graph,
    prefix_graph,
)
from prez.config import settings
from prez.reference_data.prez_ns import PREZ, ALTREXT
from prez.sparql.methods import query_to_graph, sparql_query_non_async
from prez.sparql.objects_listings import startup_count_objects
from prez.services.curie_functions import get_curie_id_for_uri

log = logging.getLogger(__name__)


async def healthcheck_sparql_endpoints():
    connected_to_triplestore = False
    log.info(f"Checking SPARQL endpoint {settings.sparql_endpoint} is online")
    username = settings.sparql_username
    password = settings.sparql_password
    if username or password:
        auth = (username, password)
    else:
        auth = None
    while not connected_to_triplestore:
        try:
            response = httpx.get(
                settings.sparql_endpoint,
                auth=auth,
                params={"query": "ASK {}"},
            )
            response.raise_for_status()
            if response.status_code == 200:
                log.info(f"Successfully connected to triplestore SPARQL endpoint")
                connected_to_triplestore = True
        except httpx.HTTPError as exc:
            log.error(f"HTTP Exception for {exc.request.url} - {exc}")
            log.error(
                f"Failed to connect to triplestore sparql endpoint {settings.sparql_endpoint}"
            )
            log.info("retrying in 3 seconds...")
            time.sleep(3)


async def count_objects():
    query = startup_count_objects()
    graph = await query_to_graph(query)
    if len(graph) > 1:
        counts_graph.__iadd__(graph)


async def populate_api_info():
    for prez in settings.prez_flavours:
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
            predicate=URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix")
        ):
            prefix_graph.bind(str(subject_objects[1]), subject_objects[0])
            log.info(
                f'Prefix "{str(subject_objects[1])}" bound to namespace {str(subject_objects[0])} from file '
                f'"{f.name}"'
            )
    log.info("Prefixes from local files added to prefix graph")

    if settings.disable_prefix_generation:
        log.info("DISABLE_PREFIX_GENERATION set to false. Skipping prefix generation.")
    else:
        query = """
            SELECT DISTINCT ?iri
            WHERE {
              ?iri ?p ?o .
              FILTER(isIRI(?iri)) 
            }
        """

        success, results = sparql_query_non_async(query)
        iris = [iri["iri"]["value"] for iri in results]
        skipped_count = 0
        skipped = []
        for iri in iris:
            try:
                get_curie_id_for_uri(iri)
            except ValueError:
                skipped_count += 1
                skipped.append(iri)

        log.info(
            f"Generated prefixes for {len(iris)} IRIs. Skipped {skipped_count} IRIs."
        )
        for skipped_iri in skipped:
            log.info(f"Skipped IRI {skipped_iri}")
