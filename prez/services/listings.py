import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import PlainTextResponse
from rdflib import URIRef, Literal
from rdflib.namespace import PROF, RDF, SH

from prez.cache import profiles_graph_cache, endpoints_graph_cache
from prez.config import settings
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.reference_data.prez_ns import ONT, PREZ
from prez.renderers.renderer import return_from_graph
from prez.services.link_generation import _add_prez_links
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import (
    temp_listing_count,
)
from prez.sparql.search_query import SearchQuery
from temp.cql2sparql import CQLParser
from temp.grammar import SubSelect
from temp.shacl2sparql import SHACLParser

log = logging.getLogger(__name__)


async def listing_function(
    request: Request,
    repo: Repo,
    system_repo: Repo,
    endpoint_uri: URIRef,
    page: int = 1,
    per_page: int = 20,
    parent_uri: Optional[URIRef] = None,
    cql_parser: CQLParser = None,
    search_term: Optional[str] = None,
):
    queries = []
    # class is from endpoint definition.
    listing_class = endpoints_graph_cache.value(endpoint_uri, ONT.deliversClasses)
    target_class = endpoints_graph_cache.value(endpoint_uri, SH.targetClass)

    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=[listing_class])
    selected_class, selected_profile = (
        prof_and_mt_info.selected_class,
        prof_and_mt_info.profile,
    )

    runtime_values = {}
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        endpoint_uri = URIRef("https://prez.dev/endpoint/system/alt-profiles-listing")
        runtime_values["selectedClass"] = listing_class

    runtime_values["limit"] = per_page
    runtime_values["offset"] = (page - 1) * per_page
    runtime_values["parent_1"] = parent_uri

    shacl_parser = SHACLParser(
        runtime_values,
        endpoints_graph_cache,
        profiles_graph_cache,
        endpoint_uri,
        selected_profile,
    )

    if cql_parser:
        cql_parser.parse()
        cql_select_ggps = cql_parser.ggps_inner_select
        shacl_parser.additional_ggps = cql_select_ggps

    shacl_parser.generate_sparql()
    main_query = shacl_parser.sparql

    if search_term:
        subselect = find_instances(shacl_parser.main_where_ggps, SubSelect)[
            0
        ]  # assume there's only one subselect
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
        # pull the subselect out of the query string
        subselect = find_instances(shacl_parser.main_where_ggps, SubSelect)[
            0
        ]  # assume there's only one subselect
        subselect.solution_modifier = None  # remove the limit and offset from the subselect so that we can get a count
        if prof_and_mt_info.profile == URIRef(
            "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
        ):
            count_class = PROF.Profile
        else:
            count_class = target_class
        if count_class:  # target_class may be unknown (None) for queries involving CQL
            queries.append(temp_listing_count(subselect, count_class))

    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        item_graph, _ = await system_repo.send_queries(queries, [])
        if "anot+" in prof_and_mt_info.mediatype:
            await _add_prez_links(item_graph, system_repo, system_repo)
    else:
        item_graph, _ = await repo.send_queries(queries, [])
        if "anot+" in prof_and_mt_info.mediatype:
            await _add_prez_links(item_graph, repo, system_repo)
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
