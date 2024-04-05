import copy
import logging
from typing import Optional, Dict

from fastapi import Request
from fastapi.responses import PlainTextResponse
from rdflib import URIRef, Literal
from rdflib.namespace import RDF, SH

from prez.cache import profiles_graph_cache, endpoints_graph_cache
from prez.config import settings
from prez.reference_data.prez_ns import PREZ, ALTREXT, ONT
from prez.renderers.renderer import return_from_graph
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.link_generation import add_prez_links
from prez.services.classes import get_classes, get_classes_single
from prez.services.query_generation.count import CountQuery, CountQueryV2
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.search import SearchQuery
from prez.services.query_generation.shacl import NodeShape
from prez.services.query_generation.umbrella import (
    merge_listing_query_grammar_inputs,
    PrezQueryConstructor,
)
from temp.grammar import *

log = logging.getLogger(__name__)


async def listing_function(
    data_repo,
    system_repo,
    endpoint_nodeshape,
    endpoint_structure,
    search_query,
    cql_parser,
    pmts,
    profile_nodeshape,
    page,
    per_page,
    order_by,
    order_by_direction,
    original_endpoint_type,
):
    if (
        pmts.selected["profile"] == ALTREXT["alt-profile"]
    ):  # recalculate the endpoint node shape
        endpoint_nodeshape_map = {
            ONT["ObjectEndpoint"]: URIRef("http://example.org/ns#AltProfilesForObject"),
            ONT["ListingEndpoint"]: URIRef(
                "http://example.org/ns#AltProfilesForListing"
            ),
        }
        endpoint_uri = endpoint_nodeshape_map[original_endpoint_type]
        endpoint_nodeshape = NodeShape(
            uri=endpoint_uri,
            graph=endpoints_graph_cache,
            kind="endpoint",
            focus_node=Var(value="focus_node"),
            path_nodes={
                "path_node_1": IRI(value=pmts.selected["class"])
            },  # hack - not sure how (or if) the class can be
            # 'dynamicaly' expressed in SHACL. The class is only known at runtime
        )

    query_construct_kwargs = merge_listing_query_grammar_inputs(
        cql_parser=cql_parser,
        endpoint_nodeshape=endpoint_nodeshape,
        search_query=search_query,
        page=page,
        per_page=per_page,
        order_by=order_by,
        order_by_direction=order_by_direction,
    )
    profile_triples = profile_nodeshape.triples_list
    profile_gpnt = profile_nodeshape.gpnt_list

    queries = []
    main_query = PrezQueryConstructor(
        profile_triples=profile_triples,
        profile_gpnt=profile_gpnt,
        **query_construct_kwargs,
    )
    queries.append(main_query.to_string())

    if (
        pmts.requested_mediatypes is not None
        and pmts.requested_mediatypes[0][0] == "application/sparql-query"
    ):
        return PlainTextResponse(queries[0], media_type="application/sparql-query")

    # add a count query if it's an annotated mediatype
    if "anot+" in pmts.selected["mediatype"] and not search_query:
        subselect = copy.deepcopy(main_query.inner_select)
        count_query = CountQueryV2(original_subselect=subselect).to_string()
        queries.append(count_query)

    # TODO absorb this up the top of function
    if pmts.selected["profile"] == ALTREXT["alt-profile"]:
        query_repo = system_repo
    else:
        query_repo = data_repo

    item_graph, _ = await query_repo.send_queries(queries, [])
    if "anot+" in pmts.selected["mediatype"]:
        await add_prez_links(item_graph, query_repo, endpoint_structure)

    # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
    if search_query:
        count = len(list(item_graph.subjects(RDF.type, PREZ.SearchResult)))
        item_graph.add((PREZ.SearchResult, PREZ["count"], Literal(count)))
    return await return_from_graph(
        item_graph,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        pmts.selected["class"],
        data_repo,
        system_repo,
    )


# async def listing_function(
#         request: Request,
#         repo: Repo,
#         system_repo: Repo,
#         endpoint_uri: URIRef,
#         hierarchy_level: int,
#         path_nodes: Dict[str, Var | IRI] = None,
#         page: int = 1,
#         per_page: int = 20,
#         cql_parser: CQLParser = None,
#         search_term: Optional[str] = None,
#         endpoint_structure: Tuple[str] = settings.endpoint_structure,
# ):
#     """
#     # determine the relevant node selection part of the query - from SHACL, CQL, Search
#     # determine the relevant profile for the query - from SHACL only
#     # gather relevant info for the node selection part of the query
#     # gather relevant info for the profile part of the query
#     # build the query
#     """
#     if not path_nodes:
#         path_nodes = {}
#     queries = []
#     # determine possible SHACL node shapes for endpoint
#     ns_triples, ns_gpnt, target_classes = await get_shacl_node_selection(
#         endpoint_uri, hierarchy_level, path_nodes, repo, system_repo
#     )
#
#     if not target_classes:
#         # then there is no target class - i.e. it's a search *only* or CQL *only* query (not SHACL + CQL or SHACL + Search)
#         if cql_parser:
#             target_classes = frozenset([PREZ.CQLObjectList])
#         elif search_term:
#             target_classes = frozenset([PREZ.SearchResult])
#
#     # determine the relevant profile
#     pmts = NegotiatedPMTs(
#         headers=request.headers,
#         params=request.query_params,
#         classes=target_classes,
#         listing=True,
#         system_repo=system_repo,
#     )
#     await pmts.setup()
#     runtime_values = {}
#     if pmts.selected["profile"] == ALTREXT["alt-profile"]:
#         endpoint_uri, ns_gpnt, ns_triples = await handle_alternate_profile(
#             current_endpoint_uri=endpoint_uri, pmts=pmts, runtime_values=runtime_values
#         )
#
#     runtime_values["limit"] = per_page
#     runtime_values["offset"] = (page - 1) * per_page
#
#     cql_triples_list = []
#     cql_gpnt_list = []
#     if cql_parser:
#         cql_triples_list = await handle_cql(cql_gpnt_list, cql_parser, cql_triples_list)
#
#     # query_construct_kwargs = merge_query_grammar_inputs(
#     #     cql_triples_list,
#     #     cql_gpnt_list,
#     #     ns_triples,
#     #     ns_gpnt,
#     #
#     # )
#     #
#     # cql_select_triples: Optional[List[SimplifiedTriple]] = None,
#     # cql_select_gpnt: Optional[List[GraphPatternNotTriples]] = None,
#     # endpoint_select_triples: Optional[List[SimplifiedTriple]] = None,
#     # endpoint_select_gpnt: Optional[List[GraphPatternNotTriples]] = None,
#     # search_query: Optional[SearchQueryRegex] = None,
#     # limit: Optional[int] = None,
#     # offset: Optional[int] = None,
#     # order_by: Optional[str] = None,
#     # order_by_direction: Optional[bool] = None,
#
#     query_constructor = PrezQueryConstructor(
#         runtime_values=runtime_values,
#         endpoint_graph=endpoints_graph_cache,
#         profile_graph=profiles_graph_cache,
#         listing_or_object="listing",
#         endpoint_uri=endpoint_uri,
#         profile_uri=pmts.selected["profile"],
#         endpoint_shacl_triples=ns_triples,
#         endpoint_shacl_gpnt=ns_gpnt,
#         cql_triples=cql_triples_list,
#         cql_gpnt=cql_gpnt_list,
#     )
#
#     query_constructor.generate_sparql()
#     main_query = query_constructor.sparql
#
#     if search_term:
#         subselect = query_constructor.inner_select
#         search_query = SearchQuery(
#             search_term=search_term,
#             pred_vals=settings.label_predicates,
#             additional_ss=subselect,
#             limit=runtime_values["limit"],
#             offset=runtime_values["offset"],
#         ).render()
#         queries.append(search_query)
#     else:
#         queries.append(main_query)
#     if (
#             pmts.requested_mediatypes is not None
#             and pmts.requested_mediatypes[0][0] == "application/sparql-query"
#     ):
#         return PlainTextResponse(queries[0], media_type="application/sparql-query")
#
#     # add a count query if it's an annotated mediatype
#     if "anot+" in pmts.selected["mediatype"] and not search_term:
#         subselect = copy.deepcopy(query_constructor.inner_select)
#         count_query = CountQuery(subselect=subselect).render().to_string()
#         queries.append(count_query)
#
#     if pmts.selected["profile"] == ALTREXT["alt-profile"]:
#         query_repo = system_repo
#         endpoint_structure = ("profiles",)
#     else:
#         query_repo = repo
#         endpoint_structure = endpoint_structure
#
#     item_graph, _ = await query_repo.send_queries(queries, [])
#     if "anot+" in pmts.selected["mediatype"]:
#         await add_prez_links(  # TODO can this go under return_from_graph?
#             item_graph, query_repo, endpoint_structure
#         )
#
#     # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
#     if search_term:
#         count = len(list(item_graph.subjects(RDF.type, PREZ.SearchResult)))
#         item_graph.add((PREZ.SearchResult, PREZ["count"], Literal(count)))
#     return await return_from_graph(
#         item_graph,
#         pmts.selected["mediatype"],
#         pmts.selected["profile"],
#         pmts.generate_response_headers(),
#         pmts.selected["class"],
#         repo,
#         system_repo,
#     )
#
#
# async def handle_cql(cql_gpnt_list, cql_parser, cql_triples_list):
#     cql_parser.parse()
#     cql_select_ggps = cql_parser.ggps_inner_select
#     if cql_select_ggps.triples_block:
#         cql_triples_list = cql_select_ggps.triples_block.triples
#     if cql_select_ggps.graph_patterns_or_triples_blocks:
#         for pattern in cql_select_ggps.graph_patterns_or_triples_blocks:
#             if isinstance(pattern, TriplesBlock):
#                 cql_triples_list += pattern.triples
#             elif isinstance(pattern, GraphPatternNotTriples):
#                 cql_gpnt_list.append(pattern)
#     return cql_triples_list


async def handle_alternate_profile(current_endpoint_uri, pmts, runtime_values):
    # determine whether we are displaying alternate profiles for a LISTING or OBJECT
    ep_type = list(endpoints_graph_cache.objects(current_endpoint_uri, RDF.type))
    if ONT["ObjectEndpoint"] in ep_type:
        nodeshape_uri = URIRef("http://example.org/ns#AltProfilesForObject")
    elif ONT["ListingEndpoint"] in ep_type:
        nodeshape_uri = URIRef("http://example.org/ns#AltProfilesForListing")
    ns = NodeShape(
        uri=nodeshape_uri,
        graph=endpoints_graph_cache,
        kind="endpoint",
        path_nodes={"path_node_1": IRI(value=pmts.selected["class"])},
    )
    ns_triples = ns.triples_list
    ns_gpnt = ns.gpnt_list
    new_endpoint_uri = URIRef("https://prez.dev/endpoint/system/alt-profile-listing")
    runtime_values["selectedClass"] = pmts.selected["class"]
    return new_endpoint_uri, ns_gpnt, ns_triples


async def get_shacl_node_selection(
    endpoint_uri, hierarchy_level, path_nodes, repo, system_repo
):
    """
    Determines the relevant nodeshape based on the endpoint, hierarchy level, and parent URI
    """
    node_selection_shape = None
    target_classes = []
    relevant_ns_query = f"""SELECT ?ns ?tc
                        WHERE {{ 
                            {endpoint_uri.n3()} <https://prez.dev/ont/relevantShapes> ?ns .
                            ?ns <http://www.w3.org/ns/shacl#targetClass> ?tc ;
                                <https://prez.dev/ont/hierarchyLevel> {hierarchy_level} .
                            }}"""
    _, r = await system_repo.send_queries([], [(None, relevant_ns_query)])
    tabular_results = r[0][1]
    distinct_ns = set([result["ns"]["value"] for result in tabular_results])
    if len(distinct_ns) == 1:  # only one possible node shape
        node_selection_shape = URIRef(tabular_results[0]["ns"]["value"])
        target_classes = [URIRef(result["tc"]["value"]) for result in tabular_results]
    elif len(distinct_ns) > 1:  # more than one possible node shape
        # try all of the available nodeshapes
        path_node_classes = {}
        for pn, uri in path_nodes.items():
            path_node_classes[pn] = await get_classes_single(URIRef(uri.value), repo)
        nodeshapes = [
            NodeShape(
                uri=URIRef(ns),
                graph=endpoints_graph_cache,
                kind="endpoint",
                path_nodes=path_nodes,
            )
            for ns in distinct_ns
        ]
        matching_nodeshapes = []
        for ns in nodeshapes:
            match_all_keys = True  # Assume a match for all keys initially

            for pn, klasses in path_node_classes.items():
                # Check if all classes for this path node are in the ns.classes_at_len at this pn
                if not all(klass in ns.classes_at_len.get(pn, []) for klass in klasses):
                    match_all_keys = False  # Found a key where not all classes match
                    break  # No need to check further for this ns

            if match_all_keys:
                matching_nodeshapes.append(ns)
        # TODO logic if there is more than one nodeshape - current default nodeshapes will only return one.
        if not matching_nodeshapes:
            raise ValueError(
                "No matching nodeshapes found for the given path nodes and hierarchy level"
            )
        node_selection_shape = matching_nodeshapes[0].uri
        target_classes = list(
            endpoints_graph_cache.objects(node_selection_shape, SH.targetClass)
        )
    ns_triples = []
    ns_gpnt = []
    if not path_nodes:
        path_nodes = {}
    if node_selection_shape:
        ns = NodeShape(
            uri=node_selection_shape,
            graph=endpoints_graph_cache,
            kind="endpoint",
            path_nodes=path_nodes,
        )
        ns_triples = ns.triples_list
        ns_gpnt = ns.gpnt_list
    return ns_triples, ns_gpnt, target_classes


def find_instances(obj, cls):
    found = []

    # Check if the object itself is an instance of the class
    if isinstance(obj, cls):
        found.append(obj)

    # If the object is iterable, iterate and search recursively
    elif isinstance(obj, dict):
        for key, value in obj.items():
            found.extend(find_instances(value, cls))
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        for item in obj:
            found.extend(find_instances(item, cls))

    # If the object has attributes, search recursively in each
    elif hasattr(obj, "__dict__"):
        for key, value in obj.__dict__.items():
            found.extend(find_instances(value, cls))

    return found
