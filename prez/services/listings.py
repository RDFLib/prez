import logging
import time
from typing import Optional

from fastapi import Request
from rdflib import SH
from rdflib import URIRef

from prez.cache import profiles_graph_cache, endpoints_graph_cache
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.reference_data.prez_ns import ONT
from prez.renderers.renderer import return_from_graph, return_profiles
from prez.services.link_generation import _add_prez_links
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import (
    temp_listing_count,
)
from temp.cql2sparql import CQLParser
from temp.grammar import SubSelect
from temp.shacl2sparql import SHACLParser

log = logging.getLogger(__name__)


async def listing_function_new(
    request: Request,
    repo: Repo,
    system_repo: Repo,
    endpoint_uri: URIRef,
    page: int = 1,
    per_page: int = 20,
    parent_uri: Optional[URIRef] = None,
    cql: dict = None,
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

    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(selected_class), prof_and_mt_info=prof_and_mt_info
        )
    runtime_values = {
        "limit": per_page,
        "offset": (page - 1) * per_page,
        "parent_1": parent_uri,
    }
    shacl_parser = SHACLParser(
        runtime_values,
        endpoints_graph_cache,
        profiles_graph_cache,
        endpoint_uri,
        selected_profile,
    )

    if cql:
        cql_parser = CQLParser(cql_json=cql)
        cql_parser.parse()
        cql_select_ggps = cql_parser.ggps_inner_select
        shacl_parser.additional_ggps = cql_select_ggps

    shacl_parser.generate_sparql()
    queries.append(shacl_parser.sparql)

    # add a count query if it's an annotated mediatype
    if "anot+" in prof_and_mt_info.mediatype:
        # pull the subselect out of the query string
        subselect = find_instances(shacl_parser.main_where_ggps, SubSelect)[
            0
        ]  # assume there's only one subselect
        subselect.solution_modifier = None  # remove the limit and offset from the subselect so that we can get a count
        queries.append(temp_listing_count(subselect, target_class))

    # if selected_class in [
    #     URIRef("https://prez.dev/ProfilesList"),
    #     PROF.Profile,
    # ]:
    #     list_graph = profiles_graph_cache.query(item_members_query).graph
    #     count_graph = profiles_graph_cache.query(count_query).graph
    #     item_graph = list_graph + count_graph
    # else:
    item_graph, _ = await repo.send_queries(
        rdf_queries=queries,
        tabular_queries=[],
    )
    if "anot+" in prof_and_mt_info.mediatype:
        await _add_prez_links(item_graph, repo, system_repo)
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
