import logging
import time
from pathlib import Path

import httpx
from rdflib import URIRef, Literal, BNode, RDF, Graph, RDFS, DCTERMS, SDO, SKOS, Dataset

from prez.cache import (
    prez_system_graph,
    profiles_graph_cache,
    counts_graph,
    prefix_graph,
    endpoints_graph_cache,
    tbox_cache,
)
from prez.config import settings
from prez.reference_data.prez_ns import PREZ, ALTREXT
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import startup_count_objects

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


async def add_prefixes_to_prefix_graph(repo: Repo):
    """
    Adds prefixes to the prefix graph
    """
    for f in (Path(__file__).parent.parent / "reference_data/prefixes").glob("*.ttl"):
        g = Graph().parse(f, format="turtle")
        for i, (s, prefix) in enumerate(
            g.subject_objects(
                predicate=URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix")
            )
        ):
            namespace = g.value(
                s, URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")
            )
            prefix_graph.bind(str(prefix), namespace)

            # prefix_graph.bind(str(subject_objects[1]), subject_objects[0])
        log.info(f"{i+1:,} prefixes bound from file {f.name}")
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

        _, rows = await repo.send_queries([], [(None, query)])
        iris = [tup["iri"]["value"] for tup in rows[0][1]]
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


async def create_endpoints_graph(repo) -> Graph:
    flavours = ["CatPrez", "SpacePrez", "VocPrez"]
    added_anything = False
    for f in (Path(__file__).parent.parent / "reference_data/endpoints").glob("*.ttl"):
        # Check if file starts with any of the flavour prefixes
        matching_flavour = next(
            (flavour for flavour in flavours if f.name.startswith(flavour.lower())),
            None,
        )
        # If the file doesn't start with any specific flavour or the matching flavour is in settings.prez_flavours, parse it.
        if not matching_flavour or (
            matching_flavour and matching_flavour in settings.prez_flavours
        ):
            endpoints_graph_cache.parse(f)
            added_anything = True
    if added_anything:
        log.info("Local endpoint definitions loaded")
    else:
        log.info("No local endpoint definitions found")
    await get_remote_endpoint_definitions(repo)


async def get_remote_endpoint_definitions(repo):
    remote_endpoints_query = f"""
PREFIX ont: <https://prez.dev/ont/>
CONSTRUCT {{
    ?endpoint ?p ?o.
}}
WHERE {{
    ?endpoint a ont:Endpoint;
              ?p ?o.
}}
    """
    g, _ = await repo.send_queries([remote_endpoints_query], [])
    if len(g) > 0:
        endpoints_graph_cache.__iadd__(g)
        log.info(f"Remote endpoint definition(s) found and added")
    else:
        log.info("No remote endpoint definitions found")


async def add_common_context_ontologies_to_tbox_cache():
    g = Dataset(default_union=True)
    for file in (
        Path(__file__).parent.parent / "reference_data/context_ontologies"
    ).glob("*.nq"):
        g.parse(file, format="nquads")
    relevant_predicates = [
        RDFS.label,
        DCTERMS.title,
        DCTERMS.description,
        SDO.name,
        SKOS.prefLabel,
        SKOS.definition,
    ]
    triples = g.triples_choices((None, relevant_predicates, None))
    for triple in triples:
        tbox_cache.add(triple)
    log.info(f"Added {len(tbox_cache):,} triples from context ontologies to TBox cache")
