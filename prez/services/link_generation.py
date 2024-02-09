import logging
from string import Template

from rdflib import Graph, Literal, URIRef, DCTERMS, BNode
from rdflib.namespace import SH, RDF

from prez.cache import endpoints_graph_cache, links_ids_graph_cache
from prez.config import settings
from prez.reference_data.prez_ns import ONT
from prez.reference_data.prez_ns import PREZ
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.model_methods import get_classes
from prez.sparql.methods import Repo
from temp.grammar import *
from temp.shacl_node_selection import NodeShape

log = logging.getLogger(__name__)


async def add_prez_links(graph: Graph, repo: Repo, endpoint_structure):
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    uris = [uri for uri in graph.all_nodes() if isinstance(uri, URIRef)]
    uri_to_klasses = {}
    for uri in uris:
        uri_to_klasses[uri] = await get_classes(uri, repo)

    for uri, klasses in uri_to_klasses.items():
        if klasses:  # need class to know which endpoints can deliver the class
            await _link_generation(uri, repo, klasses, graph, endpoint_structure)


async def _link_generation(uri: URIRef, repo: Repo, klasses, graph: Graph, endpoint_structure: str = settings.endpoint_structure):
    # check the cache
    quads = list(
        links_ids_graph_cache.quads((None, None, None, uri))
    )  # context required as not all triples that relate to links or identifiers for a particular object have that
    # object's URI as the subject
    if quads:
        for quad in quads:
            graph.add(quad[:3])
    # get the endpoints that can deliver the class
    # many node shapes to one endpoint; multiple node shapes can point to the endpoint
    else:  # generate links
        available_nodeshapes = await get_nodeshapes_constraining_class(klasses, uri)
        # run queries for available nodeshapes to get link components
        for ns in available_nodeshapes:
            if int(ns.hierarchy_level) > 1:
                results = await get_link_components(available_nodeshapes, repo)
                for result in results:
                    # if the list at tuple[1] > 0 then there's some result and a link should be generated.
                    # NB for top level links, there will be a result (the graph pattern matched) BUT the result will not form
                    # part of the link. e.g. ?path_node_1 will have result(s) but is not part of the link.
                    for solution in result[1]:
                        # create link strings
                        curie_for_uri, members_link, object_link = await create_link_strings(ns.hierarchy_level, solution, uri, endpoint_structure)
                        # add links and identifiers to graph and cache
                        await add_links_to_graph_and_cache(curie_for_uri, graph, members_link, object_link, uri)
            else:
                curie_for_uri, members_link, object_link = await create_link_strings(ns.hierarchy_level, {}, uri, endpoint_structure)
                await add_links_to_graph_and_cache(curie_for_uri, graph, members_link, object_link, uri)


async def get_nodeshapes_constraining_class(klasses, uri):
    available_nodeshapes = []
    available_nodeshape_uris = list(endpoints_graph_cache.subjects(predicate=RDF.type, object=SH.NodeShape))
    available_nodeshape_triples = list(endpoints_graph_cache.triples_choices((None, SH.targetClass, list(klasses))))
    if available_nodeshape_triples:
        for ns, _, _ in available_nodeshape_triples:
            if ns in available_nodeshape_uris:
                available_nodeshapes.append(
                    NodeShape(
                        uri=ns,
                        graph=endpoints_graph_cache,
                        focus_node=IRI(value=uri),
                    )
                )
    return available_nodeshapes


async def add_links_to_graph_and_cache(curie_for_uri, graph, members_link, object_link, uri):
    quads = []
    quads.append(
        (uri, PREZ["link"], Literal(object_link), uri)
    )
    quads.append(
        (uri, DCTERMS.identifier, Literal(curie_for_uri, datatype=PREZ.identifier), uri)
    )
    if members_link:
        existing_members_link = list(
            links_ids_graph_cache.quads((uri, PREZ["members"], None, uri))
        )
        if not existing_members_link:
            members_bn = BNode()
            quads.append(
                (uri, PREZ["members"], members_bn, uri)
            )
            quads.append(
                (members_bn, PREZ["link"], Literal(members_link), uri)
            )
    for quad in quads:
        graph.add(quad[:3])
        links_ids_graph_cache.add(quad)


async def create_link_strings(hierarchy_level, solution, uri, endpoint_structure):
    components = list(endpoint_structure[:int(hierarchy_level)])
    variables = reversed(["focus_node"] + [f"path_node_{i}" for i in range(1, len(components))])
    item_link_template = Template(
        "".join([f"/{comp}/${pattern}" for comp, pattern in zip(components, variables)]))
    curie_for_uri = get_curie_id_for_uri(uri)
    sol_values = {k: get_curie_id_for_uri(v["value"]) for k, v in solution.items()}
    object_link = item_link_template.substitute(sol_values | {"focus_node": curie_for_uri})
    members_link = None
    if len(components) < len(list(endpoint_structure)):
        members_link = object_link + "/" + endpoint_structure[len(components)]
    return curie_for_uri, members_link, object_link


async def get_link_components(available_nodeshapes, repo):
    link_queries = []
    for ns in available_nodeshapes:
        link_queries.append(
            (
                ns.uri,
                "".join(SubSelect(
                    select_clause=SelectClause(
                        variables_or_all=ns.path_nodes.values()),
                    where_clause=WhereClause(
                        group_graph_pattern=GroupGraphPattern(
                            content=GroupGraphPatternSub(
                                triples_block=TriplesBlock(
                                    triples=ns.triples_list
                                ),
                                graph_patterns_or_triples_blocks=ns.gpnt_list
                            )
                        )
                    )
                ).render())
            )
        )
    _, results = await repo.send_queries([], link_queries)
    return results
