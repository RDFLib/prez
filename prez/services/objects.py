import logging

from fastapi import Request
from fastapi.responses import PlainTextResponse
from rdflib import URIRef

from prez.cache import profiles_graph_cache, endpoints_graph_cache
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo, populate_profile_and_mediatype
from prez.reference_data.prez_ns import EP
from prez.renderers.renderer import return_from_graph
from prez.services.link_generation import add_prez_links
from prez.services.model_methods import get_classes
from prez.sparql.methods import Repo
from temp.grammar import IRI
from temp.shacl2sparql import PrezQueryConstructor

log = logging.getLogger(__name__)


async def object_function(
    request: Request,
    endpoint_uri: URIRef,
    uri: URIRef,
    request_url: str,
    repo: Repo,
    system_repo: Repo,
):
    klasses = await get_classes(uri=uri, repo=repo, endpoint=endpoint_uri)
    # ConnegP
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=klasses, system_repo=system_repo)
    await populate_profile_and_mediatype(prof_and_mt_info, system_repo)

    # handle alternate profiles
    runtime_values = {}
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        endpoint_uri = URIRef("https://prez.dev/endpoint/system/alt-profiles-listing")
        # runtime_values["selectedClass"] = prof_and_mt_info.selected_class

    # runtime_values["object"] = uri
    query_constructor = PrezQueryConstructor(
        runtime_values,
        endpoints_graph_cache,
        profiles_graph_cache,
        listing_or_object="object",
        focus_node=IRI(value=uri),
        endpoint_uri=endpoint_uri,
        profile_uri=prof_and_mt_info.profile,
    )
    query_constructor.generate_sparql()
    query = query_constructor.sparql

    req_mt = prof_and_mt_info.req_mediatypes
    if req_mt:
        if list(req_mt)[0] == "application/sparql-query":
            return PlainTextResponse(query, media_type="application/sparql-query")

    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        item_graph, _ = await system_repo.send_queries([query], [])
    else:
        item_graph, _ = await repo.send_queries([query], [])
    if "anot+" in prof_and_mt_info.mediatype:
        if not endpoint_uri == EP.object:
            await add_prez_links(item_graph, repo)
        await add_prez_links(item_graph, repo)
    return await return_from_graph(
        item_graph,
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        prof_and_mt_info.selected_class,
        repo,
    )
