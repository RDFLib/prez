import logging
import time
from pathlib import Path

import httpx
from pyoxigraph import RdfFormat
from rdflib import DCTERMS, RDF, SH, BNode, Graph, Literal, URIRef

from prez.cache import (
    counts_graph,
    endpoints_graph_cache,
    prefix_graph,
    prez_system_graph,
)
from prez.config import settings, get_reference_data_dir
from prez.reference_data.prez_ns import ONT, PREZ
from prez.repositories import Repo
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.jena_assembler_queryables import (
    transform_jena_assembler_to_queryables,
)
from prez.services.query_generation.count import startup_count_objects
from prez.services.query_generation.prefixes import PrefixQuery

log = logging.getLogger(__name__)

CQL_QUERYABLE = URIRef("http://www.opengis.net/doc/IS/cql2/1.0/Queryable")


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
                log.info("Successfully connected to triplestore SPARQL endpoint")
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
    log.info("Populated API info")


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
        log.info("Remote template query(ies) found and added")
    else:
        log.info("No remote template queries found")


async def retrieve_jena_fts_shapes(repo: Repo):
    """
    Loads Jena FTS shape definitions from both remote repo and local files.
    """

    def _log_fts_shapes(graph: Graph, shape_type: URIRef, label: str):
        shape_nodes = list(graph.subjects(RDF.type, shape_type))
        n_shapes = len(shape_nodes)
        if n_shapes > 0:
            names_list = []
            for node in shape_nodes:
                name = next(graph.objects(node, SH.name), None)
                if name is None:
                    name = next(graph.objects(node, DCTERMS.identifier), None)
                names_list.append(str(name) if name is not None else "(no label)")
            names = ", ".join(names_list)
            log.info(f"Found and added {n_shapes} {label}: {names}")
        else:
            log.info(f"No {label} found")

    # Load remote shapes
    query = """
        DESCRIBE ?fts_shape
        WHERE {
            { ?fts_shape a <https://prez.dev/ont/JenaFTSPropertyShape> }
            UNION
            { ?fts_shape a <https://prez.dev/ont/JenaFTSUnionShape> }
        }
    """
    remote_g, _ = await repo.send_queries([query], [])
    if len(remote_g) > 0:
        prez_system_graph.__iadd__(remote_g)
        _log_fts_shapes(
            remote_g,
            ONT.JenaFTSPropertyShape,
            "remote Jena FTS shapes",
        )
        _log_fts_shapes(
            remote_g,
            ONT.JenaFTSUnionShape,
            "remote Jena FTS union shapes",
        )
    else:
        log.info("No remote Jena FTS shapes found")

    # Load local shapes
    jena_fts_shapes_dir = get_reference_data_dir() / "jena_fts_shapes"
    local_g = Graph()
    for f in jena_fts_shapes_dir.glob("*.ttl"):
        local_g.parse(f, format="turtle")
    if len(local_g) > 0:
        prez_system_graph.__iadd__(local_g)
        _log_fts_shapes(
            local_g,
            ONT.JenaFTSPropertyShape,
            "local Jena FTS shapes",
        )
        _log_fts_shapes(
            local_g,
            ONT.JenaFTSUnionShape,
            "local Jena FTS union shapes",
        )
    else:
        log.info("No local Jena FTS shapes found")


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
    for f in (get_reference_data_dir() / "prefixes").glob("*.ttl"):
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
        log.info(f"Generating prefixes for {len_iris:,} IRIs.")
        skipped_count = 0
        skipped = []
        for iri in iris:
            try:
                get_curie_id_for_uri(iri)
            except ValueError:
                skipped_count += 1
                skipped.append(iri)

        log.info(
            f"Generated prefixes for {len(iris):,} IRIs. Skipped {skipped_count:,} IRIs."
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
    endpoints_root = get_reference_data_dir() / "endpoints"
    # Custom data endpoints
    if app_state.settings.custom_endpoints:
        # first try remote, if endpoints are found, use these
        g = await get_remote_endpoint_definitions(app_state.repo, ONT.DynamicEndpoint)
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
    # OGC Features endpoints
    if app_state.settings.enable_ogc_features:
        features_g = Graph()
        updated_hl_g = Graph()
        # check data repo for any OGC Features endpoint definitions
        remote_feat_ep_g = await get_remote_endpoint_definitions(
            app_state.repo, ONT.OGCFeaturesEndpoint
        )
        if remote_feat_ep_g:
            features_g = remote_feat_ep_g
        else:  # none found, use local defaults in Prez.
            for f in (endpoints_root / "features").glob("*.ttl"):
                features_g.parse(f)
        segments = [
            seg
            for seg in app_state.settings.ogc_features_mount_path.strip("/").split("/")
            if seg.startswith("{")
        ]
        mount_delta = len(segments)
        if mount_delta > 0:
            for s, p, o in features_g.triples((None, ONT.hierarchyLevel, None)):
                new_o = Literal(int(str(o)) + mount_delta)
                features_g.remove((s, p, o))
                updated_hl_g.add((s, p, new_o))
        endpoints_graph_cache.__iadd__(features_g)
        endpoints_graph_cache.__iadd__(updated_hl_g)


async def get_remote_endpoint_definitions(repo: Repo, ep_type: URIRef):
    ep_query = f"DESCRIBE ?ep {{ ?ep a {ep_type.n3()} }}"
    g, _ = await repo.send_queries([ep_query], [])
    ep_uris = list(g.subjects(RDF.type, ep_type))
    ep_nodeshape_query = (
        f"DESCRIBE ?shape {{ "
        f"VALUES ?endpoint {{ {" ".join(ep_uri.n3() for ep_uri in ep_uris)} }} "
        f"?endpoint {ONT['relevantShapes'].n3()} ?shape . "
        f"?shape {ONT['hierarchyLevel'].n3()} ?obj "
        f"}}"
    )
    if len(g) > 0:
        # get ep nodeshapes for these endpoints
        ns_g, _ = await repo.send_queries([ep_nodeshape_query], [])
        g.__iadd__(ns_g)
        log.info(f"Remote endpoint definitions found and added for type {str(ep_type)}")
        return g
    else:
        log.info(f"No remote endpoint definitions found for type {str(ep_type)}")


async def _retrieve_remote_queryable_definitions(app_state) -> Graph:
    query = "DESCRIBE ?queryable { ?queryable a <http://www.opengis.net/doc/IS/cql2/1.0/Queryable> }"
    g, _ = await app_state.repo.send_queries([query], [])
    if len(g) > 0:
        _log_queryable_graph(g, "remote")
    else:
        log.info("No remote queryable definitions found")
    return g


def _retrieve_local_queryable_definitions() -> Graph:
    queryables_dir = get_reference_data_dir() / "queryables"
    g = Graph()
    files = list(queryables_dir.glob("*.ttl")) + list(queryables_dir.glob("*.rdf"))
    for f in files:
        g.parse(f)
    if len(g) > 0:
        _log_queryable_graph(g, "local")
    else:
        log.info("No local queryable definitions found")
    return g


def _retrieve_generated_queryable_definitions(app_state) -> Graph:
    assembler_path = app_state.settings.jena_assembler_path
    if not assembler_path:
        log.info("No Jena assembler path configured for generated queryables")
        return Graph()

    assembler_file = Path(assembler_path)
    print(assembler_file.absolute())
    if not assembler_file.exists():
        raise FileNotFoundError(
            f"Configured jena_assembler_path does not exist: {assembler_file}"
        )
    if not assembler_file.is_file():
        raise ValueError(
            f"Configured jena_assembler_path is not a file: {assembler_file}"
        )

    assembler_graph = Graph().parse(assembler_file, format="turtle")
    generated_graph = transform_jena_assembler_to_queryables(assembler_graph)
    _log_queryable_graph(generated_graph, "generated")
    return generated_graph


def _log_queryable_graph(graph: Graph, source_label: str) -> None:
    queryables = list(graph.subjects(predicate=RDF.type, object=CQL_QUERYABLE))
    n_queryables = len(queryables)
    names_list = [
        f'"{str(triple[2])}"'
        for triple in graph.triples_choices((queryables, SH.name, None))
    ]
    log.info(
        f'Found and added {n_queryables} {source_label} queryables: {", ".join(names_list)}'
    )


def _copy_queryable_closure(
    source_graph: Graph,
    target_graph: Graph,
    subject: URIRef | BNode,
    seen_nodes: set[URIRef | BNode] | None = None,
) -> None:
    if seen_nodes is None:
        seen_nodes = set()
    if subject in seen_nodes:
        return
    seen_nodes.add(subject)

    for _, predicate, obj in source_graph.triples((subject, None, None)):
        target_graph.add((subject, predicate, obj))
        if isinstance(obj, BNode):
            _copy_queryable_closure(source_graph, target_graph, obj, seen_nodes)


def _queryable_merge_key(graph: Graph, subject: URIRef | BNode) -> str:
    identifier = graph.value(subject, DCTERMS.identifier)
    if identifier is not None:
        return str(identifier)
    return str(subject)


def _merge_queryable_graphs(source_graphs: list[tuple[str, Graph]]) -> Graph:
    merged_graph = Graph()
    seen_keys: set[str] = set()

    for source_label, graph in source_graphs:
        for prefix, namespace in graph.namespaces():
            merged_graph.bind(prefix, namespace)
        kept = 0
        skipped = 0
        for queryable in graph.subjects(RDF.type, CQL_QUERYABLE):
            merge_key = _queryable_merge_key(graph, queryable)
            if merge_key in seen_keys:
                skipped += 1
                continue
            _copy_queryable_closure(graph, merged_graph, queryable)
            seen_keys.add(merge_key)
            kept += 1
        log.info(
            "Merged %s queryables from %s source (%s skipped by precedence)",
            kept,
            source_label,
            skipped,
        )
    return merged_graph


def _populate_queryable_props(app_state, graph: Graph) -> None:
    app_state.queryable_props.clear()
    for subject in graph.subjects(RDF.type, CQL_QUERYABLE):
        for identifier in graph.objects(subject, DCTERMS.identifier):
            app_state.queryable_props[str(identifier)] = str(subject)


async def retrieve_queryable_definitions(app_state, system_store):
    generated_graph = _retrieve_generated_queryable_definitions(app_state)
    remote_graph = await _retrieve_remote_queryable_definitions(app_state)
    local_graph = _retrieve_local_queryable_definitions()
    merged_graph = _merge_queryable_graphs(
        [
            ("local", local_graph),
            ("remote", remote_graph),
            ("generated", generated_graph),
        ]
    )

    if len(merged_graph) == 0:
        log.info("No queryable definitions found from any source")
        app_state.queryable_props.clear()
        return

    prez_system_graph.__iadd__(merged_graph)
    queryable_bytes = merged_graph.serialize(format="nt", encoding="utf-8")
    system_store.load(queryable_bytes, RdfFormat.N_TRIPLES)
    _populate_queryable_props(app_state, merged_graph)
