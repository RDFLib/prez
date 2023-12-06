import logging

from fastapi import Request
from rdflib import URIRef

from prez.cache import profiles_graph_cache, endpoints_graph_cache
from prez.models.object_item import ObjectItem
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.reference_data.prez_ns import PREZ, EP
from prez.renderers.renderer import return_from_graph, return_profiles
from prez.services.link_generation import (
    _add_prez_links,
    _add_prez_link_to_collection_page,
)
from prez.services.model_methods import get_classes
from prez.sparql.methods import Repo
from temp.shacl2sparql import SHACLParser

log = logging.getLogger(__name__)


async def object_function_new(
    request: Request,
    endpoint_uri: URIRef,
    uri: URIRef,
    request_url: str,
    repo: Repo,
    system_repo: Repo,
):
    klasses = await get_classes(uri=uri, repo=repo, endpoint=endpoint_uri)
    # ConnegP
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=klasses)
    # if we're on the object endpoint and a profile hasn't been requested, use the open profile
    if (endpoint_uri == EP.object) and not (
        prof_and_mt_info.req_profiles or prof_and_mt_info.req_profiles_token
    ):
        prof_and_mt_info.selected_class = None
        prof_and_mt_info.profile = PREZ["profile/open"]
    # create the object with all required info
    object_item = ObjectItem(  # object item now does not need request
        uri=uri,
        classes=klasses,
        profile=prof_and_mt_info.profile,
        selected_class=prof_and_mt_info.selected_class,
    )
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(object_item.selected_class),
            prof_and_mt_info=prof_and_mt_info,
            repo=repo,
        )
    runtime_values = {"object": uri}
    shacl_parser = SHACLParser(
        runtime_values,
        endpoints_graph_cache,
        profiles_graph_cache,
        endpoint_uri,
        prof_and_mt_info.profile,
    )
    shacl_parser.generate_sparql()
    query = shacl_parser.sparql
    log.debug(f"Object Query: {query}")

    if object_item.selected_class == URIRef("http://www.w3.org/ns/dx/prof/Profile"):
        item_graph = profiles_graph_cache.query(query).graph
    else:
        item_graph, _ = await repo.send_queries([query], [])
    if "anot+" in prof_and_mt_info.mediatype:
        if not endpoint_uri == EP.object:
            await _add_prez_link_to_collection_page(
                item_graph, uri, request_url, endpoint_uri
            )
        await _add_prez_links(item_graph, repo, system_repo)
    return await return_from_graph(
        item_graph,
        prof_and_mt_info.mediatype,
        object_item.profile,
        prof_and_mt_info.profile_headers,
        prof_and_mt_info.selected_class,
        repo,
    )
