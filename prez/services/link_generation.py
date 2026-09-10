import logging
import time
from string import Template

from oxrdflib._converter import from_ox
from pyoxigraph import (
    Store as OxiStore,
    Quad as OxiQuad,
    NamedNode as OxiNamedNode,
    Literal as OxiLiteral,
    DefaultGraph as OxiDefaultGraph,
)
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SH
from sparql_grammar import (
    IRI,
    GroupGraphPattern,
    GroupGraphPatternSub,
    InlineData,
    InlineDataOneVar,
    SelectClause,
    SubSelect,
    TriplesBlock,
    Var,
    WhereClause,
)

from prez.cache import endpoints_graph_cache, links_ids_graph_cache
from prez.config import settings
from prez.reference_data.prez_ns import PREZ
from prez.repositories import Repo
from prez.services.classes import get_classes
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.query_generation.grammar_helpers import triples_block
from prez.services.query_generation.shacl import (
    NodeShape,
    clear_nodeshape_cache,
    get_nodeshape,
)

log = logging.getLogger(__name__)

#: Node shapes that describe how to reach objects, but whose endpoints do not have
#: links of this kind: CQL and search results are not addressable by a path, and the
#: OGC Features endpoints build their links in the router.
NODESHAPES_WITHOUT_LINKS = frozenset(
    URIRef(f"http://example.org/ns#{name}")
    for name in (
        "CQL",
        "Search",
        "TopConcepts",
        "Narrowers",
        "QueryablesGlobal",
        "QueryablesLocal",
        "Feature",
        "FeatureCollections",
    )
)

#: class -> the node shapes that constrain it. Finding them means scanning the
#: endpoints graph, which link generation would otherwise redo for every class of
#: every response; the shapes themselves are cached in shacl.get_nodeshape.
_nodeshapes_for_class: dict[URIRef, list[NodeShape]] = {}

#: (hierarchy level, endpoint structure) -> the link template for that depth.
_link_templates: dict[tuple[int, tuple], Template] = {}


def clear_link_generation_caches() -> None:
    """Forget the parsed node shapes and link templates."""
    _nodeshapes_for_class.clear()
    _link_templates.clear()
    clear_nodeshape_cache()


async def add_prez_links(
    graph: Graph, repo: Repo, endpoint_structure, uris: list[URIRef] | None = None
):
    """
    Adds internal links to the given graph for all URIRefs that have a class and endpoint associated with them.
    """
    t_start = time.time()
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    if uris is None:
        uri_collection_start = time.time()
        uris = [uri for uri in graph.all_nodes() if isinstance(uri, URIRef)]
        log.debug(
            f"Time taken to collect link candidate URIs from graph: {time.time() - uri_collection_start} "
            f"(unique_uris={len(uris)})"
        )
    else:
        log.debug(f"Using provided URIs for link generation: {len(uris)}")
    t = time.time()
    uriref_to_klasses = await get_classes(uris, repo)
    log.debug(f"Time taken to get classes for {len(uris)} URIs: {time.time() - t}")
    # Convert the URIRefs to OxiNamedNode because the link cache uses Oxigraph nodes as keys
    urinode_to_klasses = {
        OxiNamedNode(uri): klasses for uri, klasses in uriref_to_klasses.items()
    }
    link_generation_start = time.time()
    await _link_generation_many(urinode_to_klasses, repo, graph, endpoint_structure)
    log.debug(
        f"Time taken to generate and add links for {len(urinode_to_klasses)} URIs: "
        f"{time.time() - link_generation_start}"
    )
    log.debug(f"Total time taken to add links: {time.time() - t_start}")


async def add_prez_links_for_oxigraph(
    store: OxiStore,
    repo: Repo,
    endpoint_structure,
    uris: list[OxiNamedNode] | None = None,
):
    """
    Adds internal links to the given store for all URIRefs that have a class and endpoint associated with them.
    """
    t_start = time.time()
    log.debug(
        "Starting Prez link generation for Oxigraph store "
        f"(provided_uris={len(uris) if uris is not None else 'auto'}, store_quads={len(store)})"
    )
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    if uris is None:
        # TODO: Is there a faster way to get all unique subjects and objects in Oxigraph?
        uri_collection_start = time.time()
        unique_subjects: set[OxiNamedNode] = set()
        unique_objects: set[OxiNamedNode] = set()
        for s, p, o, c in store:
            if isinstance(s, OxiNamedNode):
                unique_subjects.add(s)
            if isinstance(o, OxiNamedNode):
                unique_objects.add(o)
        uris = list(unique_subjects.union(unique_objects))
        log.debug(
            f"Time taken to collect link candidate URIs from store: {time.time() - uri_collection_start} "
            f"(subjects={len(unique_subjects)}, objects={len(unique_objects)}, unique_uris={len(uris)})"
        )
    else:
        log.debug(f"Using provided URIs for link generation: {len(uris)}")
    t = time.time()
    # get_classes always takes URIRefs because the aiocahce pickes URIRefs
    uriref_keys = [URIRef(uri.value) for uri in uris]
    uriref_to_klasses = await get_classes(uriref_keys, repo)
    log.debug(
        f"Time taken to get classes for {len(uriref_keys)} URIs: {time.time() - t}"
    )
    # Convert the URIRefs to OxiNamedNode because the link cache uses Oxigraph nodes as keys
    urinode_to_klasses = {
        OxiNamedNode(uri): klasses for uri, klasses in uriref_to_klasses.items()
    }
    link_generation_start = time.time()
    await _link_generation_many(urinode_to_klasses, repo, store, endpoint_structure)
    log.debug(
        f"Time taken to generate and add links for {len(urinode_to_klasses)} URIs: "
        f"{time.time() - link_generation_start}"
    )
    log.debug(f"Total time taken to add links: {time.time() - t_start}")


async def _link_generation_many(
    uris_klasses: dict[OxiNamedNode, list[URIRef]],
    repo: Repo,
    graph: Graph | OxiStore,
    endpoint_structure: tuple = settings.endpoint_structure,
):
    """
    Generates links for the given URI if it is not already cached.
    """
    klasses_to_get_for_uris = dict()
    cache_hits = 0
    cache_misses = 0
    cached_quads = []
    for uri_node, klasses in uris_klasses.items():
        # check the cache
        quads = list(
            links_ids_graph_cache.quads_for_pattern(None, None, None, uri_node)
        )  # context required as not all triples that relate to links or identifiers for a particular object have that
        # object's URI as the subject
        if quads:
            cache_hits += 1
            cached_quads.extend(quads)
        else:
            cache_misses += 1
            # if no links in cache, record klass and uri to generate link components
            for klass in klasses:
                if klass not in klasses_to_get_for_uris:
                    klasses_to_get_for_uris[klass] = []
                klasses_to_get_for_uris[klass].append(uri_node)

    log.debug(f"Link cache: hits={cache_hits}, misses={cache_misses}")
    # one write for every cached link, rather than one per object
    _add_quads_to_graph(cached_quads, graph)

    # get the endpoints that can deliver the class
    # many node shapes to one endpoint; multiple node shapes can point to the endpoint
    if klasses_to_get_for_uris:  # generate links
        generated_quads = []
        for klass, uri_nodes in klasses_to_get_for_uris.items():
            available_nodeshapes = await get_nodeshapes_for_class(klass)
            # run queries for available nodeshapes to get link components
            for ns in available_nodeshapes:
                # Every hierarchy level runs the components query. Level 1 used to
                # skip it, on the reasoning that there are no path nodes to resolve
                # curies for, but the query is also what checks that the child nodes
                # exist, so skipping it generated links for empty collections (#450).
                results = await get_link_components_many(ns, uri_nodes, repo)
                for result in results:
                    # if the list at tuple[1] > 0 then there's some result and a link should be generated.
                    # NB for top level links, there will be a result (the graph pattern matched) BUT the result will not form
                    # part of the link. e.g. ?path_node_1 will have result(s) but is not part of the link.
                    solution: dict
                    for solution in result[1]:
                        uri = URIRef(
                            solution.pop("_link_focus_node")["value"]
                        )  # remove the link's focus node variable
                        # skip solutions with bnodes - can't generate valid links
                        if any(v.get("type") == "bnode" for v in solution.values()):
                            log.debug(
                                f"Skipping link generation for {uri} - solution contains bnode: {solution}"
                            )
                            continue
                        # create link strings
                        result_tuple = await create_link_strings(
                            ns.hierarchy_level,
                            solution,
                            uri,
                            endpoint_structure,
                        )
                        if result_tuple is None:
                            log.debug(
                                f"Skipping link generation for {uri} - missing required path nodes in solution: {solution}"
                            )
                            continue
                        curie_for_uri, members_link, object_link, identifiers = (
                            result_tuple
                        )
                        generated_quads.extend(
                            link_quads(
                                members_link,
                                object_link,
                                OxiNamedNode(uri),
                                identifiers,
                            )
                        )
        # one write to the cache and one to the response, rather than two per link
        links_ids_graph_cache.bulk_extend(generated_quads)
        _add_quads_to_graph(generated_quads, graph)


async def get_nodeshapes_for_class(klass: URIRef) -> list[NodeShape]:
    """The node shapes that generate links for ``klass``, parsed once and reused.

    The shapes are read, never mutated, by link generation: the components query is
    built from copies of their triple and pattern lists.
    """
    shapes = _nodeshapes_for_class.get(klass)
    if shapes is None:
        shapes = [
            ns
            for ns in await get_nodeshapes_constraining_class(
                [klass], Var(value="_link_focus_node")
            )
            if ns.uri not in NODESHAPES_WITHOUT_LINKS
        ]
        _nodeshapes_for_class[klass] = shapes
    return shapes


async def get_nodeshapes_constraining_class(klasses, focus_uri_or_var: URIRef | Var):
    """
    Retrieves the node shapes that constrain the given classes.
    """
    available_nodeshapes = []
    available_nodeshape_uris = list(
        endpoints_graph_cache.subjects(predicate=RDF.type, object=SH.NodeShape)
    )
    available_nodeshape_triples = list(
        endpoints_graph_cache.triples_choices((None, SH.targetClass, list(klasses)))
    )
    if available_nodeshape_triples:
        if isinstance(focus_uri_or_var, Var):
            _focus_node = focus_uri_or_var
        else:
            _focus_node = IRI(value=focus_uri_or_var)
        for ns, _, _ in available_nodeshape_triples:
            if ns in available_nodeshape_uris:
                available_nodeshapes.append(
                    get_nodeshape(
                        uri=ns,
                        graph=endpoints_graph_cache,
                        kind="endpoint",
                        focus_node=_focus_node,
                    )
                )
    return available_nodeshapes


def _add_quads_to_graph(quads: list[OxiQuad], graph: Graph | OxiStore) -> None:
    """Add quads as triples to a store (in one write) or an rdflib graph."""
    if not quads:
        return
    if isinstance(graph, OxiStore):
        default = OxiDefaultGraph()
        graph.bulk_extend(OxiQuad(q[0], q[1], q[2], default) for q in quads)
    else:
        graph.addN((from_ox(q[0]), from_ox(q[1]), from_ox(q[2]), graph) for q in quads)


def link_quads(
    members_link: str | None,
    object_link: str,
    uri_node: OxiNamedNode,
    identifiers: dict,
) -> list[OxiQuad]:
    """The link and identifier quads for one object, in the object's own context.

    An object gets a members link for every node shape that reaches it, so one
    object can carry several: a catalogue reached at hierarchy level 1 and again
    as a collection under another catalogue has a members link for each (#442).
    """
    quads: list[OxiQuad] = []
    quads.append(
        OxiQuad(uri_node, OxiNamedNode(PREZ["link"]), OxiLiteral(object_link), uri_node)
    )
    for uri_in_link_string, curie_in_link_string in identifiers.items():
        quads.append(
            OxiQuad(
                OxiNamedNode(uri_in_link_string),
                OxiNamedNode(PREZ.identifier),
                OxiLiteral(curie_in_link_string),
                uri_node,
            )
        )
    if members_link:
        quads.append(
            OxiQuad(
                uri_node,
                OxiNamedNode(PREZ["members"]),
                OxiLiteral(members_link),
                uri_node,
            )
        )
    return quads


def link_template(hierarchy_level: int, endpoint_structure: tuple) -> Template:
    """The URL template for objects at ``hierarchy_level``, built once per depth.

    ``/catalogs/$path_node_1/collections/$focus_node`` for level 2, say: the path
    segments come from the endpoint structure and the variables name the nodes of
    the path, outermost first.
    """
    key = (hierarchy_level, endpoint_structure)
    template = _link_templates.get(key)
    if template is None:
        components = list(endpoint_structure[:hierarchy_level])
        variables = reversed(
            ["focus_node"] + [f"path_node_{i}" for i in range(1, len(components))]
        )
        template = Template(
            "".join(
                f"/{comp}/${pattern}" for comp, pattern in zip(components, variables)
            )
        )
        _link_templates[key] = template
    return template


async def create_link_strings(
    hierarchy_level, solution, uri: URIRef, endpoint_structure: list | tuple
):
    """
    Creates link strings based on the hierarchy level and solution provided.
    Returns None if required path nodes are missing (e.g. bnodes in solution).
    """
    curie_for_uri = get_curie_id_for_uri(uri)
    identifiers = {
        URIRef(v["value"]): get_curie_id_for_uri(v["value"])
        for k, v in solution.items()
        if v.get("type") == "uri"
    } | {uri: curie_for_uri}
    hierarchy_level = int(hierarchy_level)
    endpoint_structure = tuple(endpoint_structure)
    required_path_nodes = [
        f"path_node_{i}" for i in range(1, len(endpoint_structure[:hierarchy_level]))
    ]
    sol_values = {
        k: identifiers[URIRef(v["value"])]
        for k, v in solution.items()
        if v.get("type") == "uri"
    }
    # Check all required path nodes are present
    if not all(pn in sol_values for pn in required_path_nodes):
        return None
    object_link = link_template(hierarchy_level, endpoint_structure).substitute(
        sol_values | {"focus_node": curie_for_uri}
    )
    members_link = None
    if hierarchy_level < len(endpoint_structure):
        members_link = object_link + "/" + endpoint_structure[hierarchy_level]
    return curie_for_uri, members_link, object_link, identifiers


async def get_link_components_many(
    ns: NodeShape, for_focus_nodes: list[OxiNamedNode], repo: Repo
):
    """
    Retrieves link components for the given node shape.

    Of the form:
    SELECT ?path_node_1
    WHERE {
    ?path_node_1 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/dcat#Catalog> .
    <https://example.com/TopLevelCatalogTwo> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?focus_classes .
    ?path_node_1 <http://purl.org/dc/terms/hasPart> <https://example.com/CatalogTwo> .
        VALUES ?focus_classes{ <http://www.opengis.net/ont/geosparql#FeatureCollection> <http://www.w3.org/2004/02/skos/core#ConceptScheme> <http://www.w3.org/2004/02/skos/core#Collection> <http://www.w3.org/ns/dcat#Catalog>  }
    }
    """
    link_queries = []
    if ns.path_nodes:
        link_focus_var = Var(value="_link_focus_node")
        # VALUES ?_link_focus_node { <uri1> <uri2> ... }
        _link_focus_gpnt = InlineData(
            InlineDataOneVar(
                link_focus_var, [IRI(value=n.value) for n in for_focus_nodes]
            )
        )
        # The type constraints for the focus node itself are not needed: the focus
        # nodes arrive as known IRIs. Those for the other nodes of the path are, so
        # they come across from the exists lists rather than being dropped with them.
        type_triples_not_for_focus_node = [
            tssp for tssp in ns.tssp_exists_list if tssp.subject != link_focus_var
        ]
        ttnffn_list = (
            [triples_block(type_triples_not_for_focus_node)]
            if type_triples_not_for_focus_node
            else []
        )
        focus_classes = Var(value="focus_classes")
        gpnt_exists_not_for_focus_node = [
            gpnt
            for gpnt in ns.gpnt_exists_list
            if getattr(getattr(gpnt, "data_block", None), "variable", None)
            != focus_classes
        ]
        subselect_string = SubSelect(
            select_clause=SelectClause([link_focus_var] + list(ns.path_nodes.values())),
            where_clause=WhereClause(
                GroupGraphPattern(
                    GroupGraphPatternSub(
                        # already in emission order, chosen for performance
                        [
                            TriplesBlock(list(ns.tssp_list)),
                            *ns.gpnt_list,
                            _link_focus_gpnt,
                            *ttnffn_list,
                            *gpnt_exists_not_for_focus_node,
                        ]
                    )
                )
            ),
        ).to_string()
        link_queries.append((ns.uri, subselect_string))
        _, results = await repo.send_queries([], link_queries)
        return results
    return []
