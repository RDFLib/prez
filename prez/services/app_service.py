import logging
import time
from pathlib import Path

import httpx
from rdflib import URIRef, Literal, Graph, RDF, BNode, DCTERMS

from prez.cache import (
    prez_system_graph,
    counts_graph,
    prefix_graph,
    endpoints_graph_cache,
)
from prez.config import settings
from prez.reference_data.prez_ns import PREZ, ONT
from prez.repositories import Repo
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.query_generation.count import startup_count_objects
from prez.services.query_generation.prefixes import PrefixQuery

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


async def count_objects(repo):
    query = startup_count_objects()
    graph, _ = await repo.send_queries([query], [])
    if len(graph) > 1:
        counts_graph.__iadd__(graph)


async def populate_api_info():
    prez_system_graph.add(
        (URIRef(settings.system_uri), PREZ.version, Literal(settings.prez_version))
    )
    log.info(f"Populated API info")


async def prefix_initialisation(repo: Repo):
    """
    Adds prefixes defined using the vann ontology to the prefix graph.
    Note due to the ordering, remote prefixes (typically user defined) will override local prefixes.
    Generates prefixes for IRIs which do not have one unless the "disable_prefix_generation" environment variable is
    set.
    """
    await add_remote_prefixes(repo)
    await add_local_prefixes(repo)
    await generate_prefixes(repo)


async def retrieve_remote_template_queries(repo: Repo):
    # TODO allow mediatype specification in repo queries
    query = """
        PREFIX prez: <https://prez.dev/ont/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?query ?endpoint
        WHERE {
            ?bn a prez:TemplateQuery ;
                  rdf:value ?query ;
                  prez:forEndpoint ?endpoint ;
        }
    """
    _, results = await repo.send_queries([], [(None, query)])
    if results[0][1]:
        for result in results[0][1]:
            bn = BNode()
            query = result["query"]["value"]
            endpoint = result["endpoint"]["value"]
            prez_system_graph.add((bn, RDF.type, ONT.TemplateQuery))
            prez_system_graph.add((bn, RDF.value, Literal(query)))
            prez_system_graph.add((bn, ONT.forEndpoint, URIRef(endpoint)))
        log.info(f"Remote template query(ies) found and added")
    else:
        log.info("No remote template queries found")


async def add_remote_prefixes(repo: Repo):
    # TODO allow mediatype specification in repo queries
    query = PrefixQuery().to_string()
    results = await repo.send_queries(rdf_queries=[], tabular_queries=[(None, query)])
    i = 0
    for i, result in enumerate(results[1][0][1]):
        namespace = result["namespace"]["value"]
        prefix = result["prefix"]["value"]
        prefix_graph.bind(prefix, namespace)
    log.info(f"{i + 1:,} prefixes bound from data repo")


async def add_local_prefixes(repo):
    """
    Adds prefixes to the prefix graph
    """
    for f in (Path(__file__).parent.parent / "reference_data/prefixes").glob("*.ttl"):
        g = Graph().parse(f, format="turtle")
        local_i = await _add_prefixes_from_graph(g)
        log.info(f"{local_i + 1:,} prefixes bound from file {f.name}")


async def generate_prefixes(repo: Repo):
    if settings.disable_prefix_generation:
        log.info("DISABLE_PREFIX_GENERATION set to true. Skipping prefix generation.")
    else:
        query = """
            SELECT DISTINCT ?iri
            WHERE {
              ?iri ?p ?o .
              FILTER(isIRI(?iri))
            }
        """

        _, rows = await repo.send_queries([], [(None, query)])
        iris = [tup["iri"]["value"] for tup in rows[0][1]]
        len_iris = len(iris)
        log.info(f"Generating prefixes for {len_iris} IRIs.")
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


async def _add_prefixes_from_graph(g):
    i = 0
    for i, (s, prefix) in enumerate(
            g.subject_objects(
                predicate=URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix")
            )
    ):
        namespace = g.value(
            s, URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")
        )
        prefix_graph.bind(str(prefix), namespace)
    return i


async def create_endpoints_graph(app_state):
    endpoints_root = Path(__file__).parent.parent / "reference_data/endpoints"
    # OGC Features endpoints
    if app_state.settings.enable_ogc_features:
        for f in (endpoints_root / "features").glob("*.ttl"):
            endpoints_graph_cache.parse(f)
    # Custom data endpoints
    if app_state.settings.custom_endpoints:
        # first try remote, if endpoints are found, use these
        g = await get_remote_endpoint_definitions(app_state.repo)
        if g:
            endpoints_graph_cache.__iadd__(g)
        else:
            for f in (endpoints_root / "data_endpoints_custom").glob("*.ttl"):
                endpoints_graph_cache.parse(f)
                log.info("Custom endpoints loaded from local file")
    # Default data endpoints
    else:
        for f in (endpoints_root / "data_endpoints_default").glob("*.ttl"):
            endpoints_graph_cache.parse(f)
    # Base endpoints
    for f in (endpoints_root / "base").glob("*.ttl"):
        endpoints_graph_cache.parse(f)


async def get_remote_endpoint_definitions(repo):
    listing_ep_query = f"DESCRIBE ?ep {{ ?ep a {ONT['ListingEndpoint'].n3()} }}"
    object_ep_query = f"DESCRIBE ?ep {{ ?ep a {ONT['ObjectEndpoint'].n3()} }}"
    ep_nodeshape_query = f"DESCRIBE ?shape {{ ?shape {ONT['hierarchyLevel'].n3()} ?obj }}"
    g, _ = await repo.send_queries([listing_ep_query, object_ep_query, ep_nodeshape_query], [])
    if len(g) > 0:
        log.info(f"Remote endpoint definition(s) found and added")
        return g
    else:
        log.info("No remote endpoint definitions found")


async def retrieve_remote_queryable_definitions(app_state, system_store):
    query = "DESCRIBE ?queryable { ?queryable a <http://www.opengis.net/doc/IS/cql2/1.0/Queryable> }"
    g, _ = await app_state.repo.send_queries([query], [])
    if len(g) > 0:
        prez_system_graph.__iadd__(g)  # use for generating property shapes
        queryable_bytes = g.serialize(
            format="nt", encoding="utf-8"
        )  # use for generating JSON
        system_store.load(queryable_bytes, "application/n-triples")
        queryables = list(
            g.subjects(
                object=URIRef("http://www.opengis.net/doc/IS/cql2/1.0/Queryable")
            )
        )
        for triple in list(g.triples_choices((queryables, DCTERMS.identifier, None))):
            app_state.queryable_props[str(triple[2])] = str(triple[0])
        n_queryables = len(queryables)
        log.info(f"Remote queryable definition(s) found and added: {n_queryables}")
    else:
        log.info("No remote queryable definitions found")
