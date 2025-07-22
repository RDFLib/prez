import logging
import time
from string import Template

from pyoxigraph import Store as OxiStore, Quad as OxiQuad, NamedNode as OxiNamedNode, Literal as OxiLiteral, DefaultGraph as OxiDefaultGraph
from oxrdflib._converter import to_ox, from_ox
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SH
from sparql_grammar_pydantic import (
    IRI,
    DataBlock,
    DataBlockValue,
    GraphPatternNotTriples,
    InlineData,
    InlineDataOneVar,
    Var,
    GroupGraphPattern,
    GroupGraphPatternSub,
    SelectClause,
    SubSelect,
    TriplesBlock,
    WhereClause,
)

from prez.cache import endpoints_graph_cache, links_ids_graph_cache
from prez.config import settings
from prez.reference_data.prez_ns import PREZ
from prez.repositories import Repo
from prez.services.classes import get_classes
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.query_generation.shacl import NodeShape

log = logging.getLogger(__name__)


async def add_prez_links(
    graph: Graph, repo: Repo, endpoint_structure, uris: list[URIRef] | None = None
):
    """
    Adds internal links to the given graph for all URIRefs that have a class and endpoint associated with them.
    """
    t_start = time.time()
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    if uris is None:
        uris = [uri for uri in graph.all_nodes() if isinstance(uri, URIRef)]
    t = time.time()
    uriref_to_klasses = await get_classes(uris, repo)
    log.debug(f"Time taken to get classes: {time.time() - t}")
    # Convert the URIRefs to OxiNamedNode because the link cache uses Oxigraph nodes as keys
    urinode_to_klasses = {OxiNamedNode(uri): klasses for uri, klasses in uriref_to_klasses.items()}
    await _link_generation_many(urinode_to_klasses, repo, graph, endpoint_structure)
    log.debug(f"Time taken to add links: {time.time() - t_start}")

async def add_prez_links_for_oxigraph(
    store: OxiStore, repo: Repo, endpoint_structure, uris: list[OxiNamedNode] | None = None
):
    """
    Adds internal links to the given store for all URIRefs that have a class and endpoint associated with them.
    """
    t_start = time.time()
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    if uris is None:
        # TODO: Is there a faster way to get all unique subjects and objects in Oxigraph?
        unique_subjects: set[OxiNamedNode] = set()
        unique_objects: set[OxiNamedNode] = set()
        for (s,p,o,c) in store:
            if isinstance(s, OxiNamedNode):
                unique_subjects.add(s)
            if isinstance(o, OxiNamedNode):
                unique_objects.add(o)
        uris = list(unique_subjects.union(unique_objects))
    t = time.time()
    # get_classes always takes URIRefs because the aiocahce pickes URIRefs
    uriref_keys = [URIRef(uri.value) for uri in uris]
    uriref_to_klasses = await get_classes(uriref_keys, repo)
    log.debug(f"Time taken to get classes: {time.time() - t}")
    # Convert the URIRefs to OxiNamedNode because the link cache uses Oxigraph nodes as keys
    urinode_to_klasses = {OxiNamedNode(uri): klasses for uri, klasses in uriref_to_klasses.items()}
    await _link_generation_many(urinode_to_klasses, repo, store, endpoint_structure)
    log.debug(f"Time taken to add links: {time.time() - t_start}")

async def _link_generation(
    uri_node: OxiNamedNode,
    repo: Repo,
    klasses,
    graph: Graph|OxiStore,
    endpoint_structure: tuple = settings.endpoint_structure,
):
    """
    Generates links for the given URI if it is not already cached.
    """
    is_oxigraph = isinstance(graph, OxiStore)
    # check the cache
    quads = list(
        links_ids_graph_cache.quads_for_pattern(None, None, None, uri_node)
    )  # context required as not all triples that relate to links or identifiers for a particular object have that
    # object's URI as the subject
    if quads:
        if is_oxigraph:
            store: OxiStore = graph
            default = OxiDefaultGraph()
            store.bulk_extend(OxiQuad(q[0], q[1], q[2], default) for q in quads)
        else:
            for q in quads:
                graph.add((from_ox(q[0]), from_ox(q[1]), from_ox(q[2])))
    # get the endpoints that can deliver the class
    # many node shapes to one endpoint; multiple node shapes can point to the endpoint
    else:  # generate links
        uri = URIRef(uri_node.value)
        available_nodeshapes = await get_nodeshapes_constraining_class(klasses, uri)
        # ignore CQL and Search nodeshapes as we do not want to generate links for these.
        available_nodeshapes = [
            ns
            for ns in available_nodeshapes
            if ns.uri
            not in [
                URIRef("http://example.org/ns#CQL"),
                URIRef("http://example.org/ns#Search"),
                URIRef("http://example.org/ns#TopConcepts"),
                URIRef("http://example.org/ns#Narrowers"),
                URIRef("http://example.org/ns#QueryablesGlobal"),
                URIRef("http://example.org/ns#QueryablesLocal"),
                URIRef(
                    "http://example.org/ns#Feature"
                ),  # creation of these links is hardcoded in the OGC Features API
                URIRef(
                    "http://example.org/ns#FeatureCollections"
                ),  # creation of these links is hardcoded in the OGC Features API
            ]
        ]
        # run queries for available nodeshapes to get link components
        for ns in available_nodeshapes:
            if int(ns.hierarchy_level) > 1:
                results = await get_link_components(ns, repo)
                for result in results:
                    # if the list at tuple[1] > 0 then there's some result and a link should be generated.
                    # NB for top level links, there will be a result (the graph pattern matched) BUT the result will not form
                    # part of the link. e.g. ?path_node_1 will have result(s) but is not part of the link.
                    for solution in result[1]:
                        # create link strings
                        (curie_for_uri, members_link, object_link, identifiers) = (
                            await create_link_strings(
                                ns.hierarchy_level, solution, uri, endpoint_structure
                            )
                        )
                        # add links and identifiers to graph and cache
                        await add_links_to_graph_and_cache(
                            curie_for_uri,
                            graph,
                            members_link,
                            object_link,
                            uri_node,
                            identifiers,
                        )
            else:
                curie_for_uri, members_link, object_link, identifiers = (
                    await create_link_strings(
                        ns.hierarchy_level, {}, uri, endpoint_structure
                    )
                )
                await add_links_to_graph_and_cache(
                    curie_for_uri, graph, members_link, object_link, uri_node, identifiers
                )

async def _link_generation_many(
    uris_klasses: dict[OxiNamedNode, list[URIRef]],
    repo: Repo,
    graph: Graph|OxiStore,
    endpoint_structure: tuple = settings.endpoint_structure,
):
    """
    Generates links for the given URI if it is not already cached.
    """
    is_oxigraph = isinstance(graph, OxiStore)
    klasses_to_get_for_uris = dict()
    for uri_node, klasses in uris_klasses.items():
        # check the cache
        quads = list(
            links_ids_graph_cache.quads_for_pattern(None, None, None, uri_node)
        )  # context required as not all triples that relate to links or identifiers for a particular object have that
        # object's URI as the subject
        if quads:
            if is_oxigraph:
                store: OxiStore = graph
                default = OxiDefaultGraph()
                store.bulk_extend(OxiQuad(q[0], q[1], q[2], default) for q in quads)
            else:
                for q in quads:
                    graph.add((from_ox(q[0]), from_ox(q[1]), from_ox(q[2])))
        else:
            # if no links in cache, record klass and uri to generate link components
            for klass in klasses:
                if klass not in klasses_to_get_for_uris:
                    klasses_to_get_for_uris[klass] = []
                klasses_to_get_for_uris[klass].append(uri_node)

    # get the endpoints that can deliver the class
    # many node shapes to one endpoint; multiple node shapes can point to the endpoint
    if klasses_to_get_for_uris:  # generate links
        for klass, uri_nodes in klasses_to_get_for_uris.items():
            available_nodeshapes = await get_nodeshapes_constraining_class([klass], Var(value="_link_focus_node"))
            # ignore CQL and Search nodeshapes as we do not want to generate links for these.
            available_nodeshapes = [
                ns
                for ns in available_nodeshapes
                if ns.uri
                not in [
                    URIRef("http://example.org/ns#CQL"),
                    URIRef("http://example.org/ns#Search"),
                    URIRef("http://example.org/ns#TopConcepts"),
                    URIRef("http://example.org/ns#Narrowers"),
                    URIRef("http://example.org/ns#QueryablesGlobal"),
                    URIRef("http://example.org/ns#QueryablesLocal"),
                    URIRef(
                        "http://example.org/ns#Feature"
                    ),  # creation of these links is hardcoded in the OGC Features API
                    URIRef(
                        "http://example.org/ns#FeatureCollections"
                    ),  # creation of these links is hardcoded in the OGC Features API
                ]
            ]
            # run queries for available nodeshapes to get link components
            for ns in available_nodeshapes:
                if int(ns.hierarchy_level) > 1:
                    results = await get_link_components_many(ns, uri_nodes, repo)
                    for result in results:
                        # if the list at tuple[1] > 0 then there's some result and a link should be generated.
                        # NB for top level links, there will be a result (the graph pattern matched) BUT the result will not form
                        # part of the link. e.g. ?path_node_1 will have result(s) but is not part of the link.
                        solution: dict
                        for solution in result[1]:
                            uri = URIRef(solution.pop("_link_focus_node")["value"])  # remove the link's focus node variable
                            # create link strings
                            (curie_for_uri, members_link, object_link, identifiers) = (
                                await create_link_strings(
                                    ns.hierarchy_level, solution, uri, endpoint_structure
                                )
                            )
                            uri_node = OxiNamedNode(uri)
                            # add links and identifiers to graph and cache
                            await add_links_to_graph_and_cache(
                                curie_for_uri,
                                graph,
                                members_link,
                                object_link,
                                uri_node,
                                identifiers,
                            )
                else:
                    for uri_node in uri_nodes:
                        curie_for_uri, members_link, object_link, identifiers = (
                            await create_link_strings(
                                ns.hierarchy_level, {}, URIRef(uri_node.value), endpoint_structure
                            )
                        )
                        await add_links_to_graph_and_cache(
                            curie_for_uri, graph, members_link, object_link, uri_node, identifiers
                        )


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
                    NodeShape(
                        uri=ns,
                        graph=endpoints_graph_cache,
                        kind="endpoint",
                        focus_node=_focus_node,
                    )
                )
    return available_nodeshapes


async def add_links_to_graph_and_cache(
    curie_for_uri,
    graph: Graph | OxiStore,
    members_link: str|None,
    object_link: str,
    uri_node: OxiNamedNode,
    identifiers: dict
):
    """
    Adds links and identifiers to the given graph and cache.
    """
    quads: list[OxiQuad] = []
    quads.append(OxiQuad(uri_node, OxiNamedNode(PREZ["link"]), OxiLiteral(object_link), uri_node))
    for uri_in_link_string, curie_in_link_string in identifiers.items():
        quads.append(
            OxiQuad(OxiNamedNode(uri_in_link_string), OxiNamedNode(PREZ.identifier), OxiLiteral(curie_in_link_string), uri_node)
        )
    if (members_link):
        # TODO need to confirm the link value doesn't match the existing link value, as multiple endpoints can deliver
        # the same class/have different links for the same URI
        existing_members_link = list(
            links_ids_graph_cache.quads_for_pattern(uri_node, OxiNamedNode(PREZ["members"]), None, uri_node)
        )
        if not existing_members_link:
            quads.append(OxiQuad(uri_node, OxiNamedNode(PREZ["members"]), OxiLiteral(members_link), uri_node))
    links_ids_graph_cache.bulk_extend(quads)
    if isinstance(graph, OxiStore):
        store: OxiStore = graph
        default = OxiDefaultGraph()
        store.bulk_extend(OxiQuad(q[0], q[1], q[2], default) for q in quads)
    else:
        for q in quads:
            graph.add((from_ox(q[0]), from_ox(q[1]), from_ox(q[2])))


async def create_link_strings(hierarchy_level, solution, uri: URIRef, endpoint_structure: list|tuple):
    """
    Creates link strings based on the hierarchy level and solution provided.
    """
    curie_for_uri = get_curie_id_for_uri(uri)
    identifiers = {
        URIRef(v["value"]): get_curie_id_for_uri(v["value"])
        for k, v in solution.items()
    } | {uri: curie_for_uri}
    components = list(endpoint_structure[: int(hierarchy_level)])
    variables = reversed(
        ["focus_node"] + [f"path_node_{i}" for i in range(1, len(components))]
    )
    item_link_template = Template(
        "".join([f"/{comp}/${pattern}" for comp, pattern in zip(components, variables)])
    )
    sol_values = {k: identifiers[URIRef(v["value"])] for k, v in solution.items()}
    object_link = item_link_template.substitute(
        sol_values | {"focus_node": curie_for_uri}
    )
    members_link = None
    if len(components) < len(list(endpoint_structure)):
        members_link = object_link + "/" + endpoint_structure[len(components)]
    return curie_for_uri, members_link, object_link, identifiers


async def get_link_components(ns: NodeShape, repo: Repo):
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
        link_queries.append(
            (
                ns.uri,
                SubSelect(
                    select_clause=SelectClause(variables_or_all=ns.path_nodes.values()),
                    where_clause=WhereClause(
                        group_graph_pattern=GroupGraphPattern(
                            content=GroupGraphPatternSub(
                                triples_block=TriplesBlock.from_tssp_list(
                                    ns.tssp_list[::-1]
                                ),  # reversed for performance
                                graph_patterns_or_triples_blocks=ns.gpnt_list,
                            )
                        )
                    ),
                ).to_string(),
            )
        )
        _, results = await repo.send_queries([], link_queries)
        return results
    return []

async def get_link_components_many(ns: NodeShape, for_focus_nodes: list[OxiNamedNode], repo: Repo):
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
        _link_focus_gpnt = GraphPatternNotTriples(
            content=InlineData(
                data_block=DataBlock(
                    block=InlineDataOneVar(
                        variable=link_focus_var,
                        datablockvalues=[
                            DataBlockValue(value=IRI(value=n.value)) for n in for_focus_nodes
                            ],
                    )
                )
            )
        )
        subselect_string = SubSelect(
                    select_clause=SelectClause(variables_or_all=[link_focus_var]+list(ns.path_nodes.values())),
                    where_clause=WhereClause(
                        group_graph_pattern=GroupGraphPattern(
                            content=GroupGraphPatternSub(
                                triples_block=TriplesBlock.from_tssp_list(
                                    ns.tssp_list[::-1]
                                ),  # reversed for performance
                                graph_patterns_or_triples_blocks=ns.gpnt_list+[_link_focus_gpnt],
                            )
                        )
                    ),
                ).to_string()
        link_queries.append((ns.uri, subselect_string))
        _, results = await repo.send_queries([], link_queries)
        return results
    return []