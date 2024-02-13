import copy
import logging
from typing import Optional, Dict

from fastapi import Request
from fastapi.responses import PlainTextResponse
from rdflib import URIRef, Literal
from rdflib.namespace import RDF, SH
from rdframe import CQLParser

from prez.cache import profiles_graph_cache, endpoints_graph_cache
from prez.config import settings
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo, populate_profile_and_mediatype
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph
from prez.services.link_generation import add_prez_links
from prez.services.query_generation.classes import get_classes
from prez.services.query_generation.count import CountQuery
from prez.repositories import Repo
from prez.services.query_generation.search import SearchQuery
from temp.grammar import *
# from rdframe.grammar import SubSelect
# from rdframe import PrezQueryConstructor
from prez.services.query_generation.umbrella import PrezQueryConstructor
from prez.services.query_generation.shacl_node_selection import NodeShape

log = logging.getLogger(__name__)


async def listing_function(
        request: Request,
        repo: Repo,
        system_repo: Repo,
        endpoint_uri: URIRef,
        hierarchy_level: int,
        path_nodes: Dict[str, Var | IRI] = None,
        page: int = 1,
        per_page: int = 20,
        parent_uri: Optional[URIRef] = None,
        cql_parser: CQLParser = None,
        search_term: Optional[str] = None,
        endpoint_structure: Tuple[str] = settings.endpoint_structure,
):
    """
    # determine the relevant node selection part of the query - from SHACL, CQL, Search
    # determine the relevant profile for the query - from SHACL only
    # gather relevant info for the node selection part of the query
    # gather relevant info for the profile part of the query
    # build the query
    """
    queries = []
    # determine possible SHACL node shapes for endpoint
    node_selection_shape, target_classes = await determine_nodeshape(
        endpoint_uri, hierarchy_level, parent_uri, path_nodes, repo, system_repo)

    if not path_nodes:
        path_nodes = {}
    ns = NodeShape(uri=node_selection_shape, graph=endpoints_graph_cache, path_nodes=path_nodes)

    # determine the relevant profile
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=target_classes, system_repo=system_repo,
                                              listing=True)
    await populate_profile_and_mediatype(prof_and_mt_info, system_repo)
    selected_class, selected_profile = (
        prof_and_mt_info.selected_class,
        prof_and_mt_info.profile,
    )

    runtime_values = {}
    if prof_and_mt_info.profile == URIRef(
            "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        endpoint_uri = URIRef("https://prez.dev/endpoint/system/alt-profiles-listing")
        runtime_values["selectedClass"] = prof_and_mt_info.selected_class

    runtime_values["limit"] = per_page
    runtime_values["offset"] = (page - 1) * per_page

    query_constructor = PrezQueryConstructor(
        runtime_values,
        endpoints_graph_cache,
        profiles_graph_cache,
        listing_or_object="listing",
        endpoint_uri=endpoint_uri,
        profile_uri=selected_profile,
        node_selection_triples=ns.triples_list,
        node_selection_gpnt=ns.gpnt_list,
        target_class=target_classes
    )

    if cql_parser:
        cql_parser.parse()
        cql_select_ggps = cql_parser.ggps_inner_select
        query_constructor.additional_ggps = cql_select_ggps

    query_constructor.generate_sparql()
    main_query = query_constructor.sparql

    if search_term:
        subselect = query_constructor.inner_select
        search_query = SearchQuery(
            search_term=search_term,
            pred_vals=settings.label_predicates,
            additional_ss=subselect,
            limit=runtime_values["limit"],
            offset=runtime_values["offset"],
        ).render()
        queries.append(search_query)
    else:
        queries.append(main_query)
    req_mt = prof_and_mt_info.req_mediatypes
    if req_mt:
        if list(req_mt)[0] == "application/sparql-query":
            return PlainTextResponse(queries[0], media_type="application/sparql-query")

    # add a count query if it's an annotated mediatype
    if "anot+" in prof_and_mt_info.mediatype and not search_term:
        subselect = copy.deepcopy(query_constructor.inner_select)
        subselect.solution_modifier = None  # remove the limit and offset from the subselect so that we can get a count
        count_query = CountQuery(subselect=subselect).render()
        queries.append(count_query)

        # if prof_and_mt_info.profile == URIRef(
        #     "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
        # ):
        #     count_class = PROF.Profile
        # else:
        #     count_class = target_classes
        # if count_class:  # target_class may be unknown (None) for queries involving CQL
        #     queries.append(temp_listing_count(subselect, count_class))

    if prof_and_mt_info.profile == URIRef(
            "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        item_graph, _ = await system_repo.send_queries(queries, [])
        if "anot+" in prof_and_mt_info.mediatype:
            await add_prez_links(item_graph, system_repo, endpoint_structure)
    else:
        item_graph, _ = await repo.send_queries(queries, [])
        if "anot+" in prof_and_mt_info.mediatype:
            await add_prez_links(item_graph, repo, endpoint_structure)
    # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
    if search_term:
        count = len(list(item_graph.subjects(RDF.type, PREZ.SearchResult)))
        item_graph.add((PREZ.SearchResult, PREZ["count"], Literal(count)))
    return await return_from_graph(
        item_graph,
        prof_and_mt_info.mediatype,
        selected_profile,
        prof_and_mt_info.profile_headers,
        prof_and_mt_info.selected_class,
        repo,
    )


async def determine_nodeshape(endpoint_uri, hierarchy_level, parent_uri, path_nodes, repo, system_repo):
    node_selection_shape = None
    target_classes = []
    relevant_ns_query = f"""SELECT ?ns ?tc
                        WHERE {{ 
                            {endpoint_uri.n3()} <https://prez.dev/ont/relevantShapes> ?ns .
                            ?ns <http://www.w3.org/ns/shacl#targetClass> ?tc ;
                                <https://prez.dev/ont/hierarchyLevel> {hierarchy_level} .
                            }}"""
    _, r = await system_repo.send_queries([], [(parent_uri, relevant_ns_query)])
    tabular_results = r[0][1]
    distinct_ns = set([result["ns"]["value"] for result in tabular_results])
    if len(distinct_ns) == 1:  # only one possible node shape
        node_selection_shape = URIRef(tabular_results[0]["ns"]["value"])
        target_classes = [URIRef(result["tc"]["value"]) for result in tabular_results]
    elif len(distinct_ns) > 1:  # more than one possible node shape
        # try all of the available nodeshapes
        path_node_classes = {}
        for pn, uri in path_nodes.items():
            path_node_classes[pn] = await get_classes(URIRef(uri.value), repo)
        nodeshapes = [NodeShape(uri=URIRef(ns), graph=endpoints_graph_cache, path_nodes=path_nodes) for ns in
                      distinct_ns]
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
        node_selection_shape = matching_nodeshapes[0].uri
        target_classes = list(endpoints_graph_cache.objects(node_selection_shape, SH.targetClass))
    return node_selection_shape, target_classes




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
