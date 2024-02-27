import logging
from typing import Tuple

from fastapi import Request
from fastapi.responses import PlainTextResponse
from rdflib import URIRef

from prez.cache import endpoints_graph_cache, profiles_graph_cache
from prez.config import settings
from prez.reference_data.prez_ns import EP
from prez.renderers.renderer import return_from_graph
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.link_generation import add_prez_links
from prez.services.query_generation.classes import get_classes
from prez.services.query_generation.umbrella import PrezQueryConstructor
from temp.grammar import IRI

log = logging.getLogger(__name__)


async def object_function(
    request: Request,
    endpoint_uri: URIRef,
    uri: URIRef,
    repo: Repo,
    system_repo: Repo,
    endpoint_structure: Tuple[str] = settings.endpoint_structure,
):
    classes = await get_classes(uri=uri, repo=repo)
    pmts = NegotiatedPMTs(**{"headers": request.headers, "params": request.query_params, "classes": classes})
    # handle alternate profiles
    runtime_values = {}
    if pmts.selected["profile"] == URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"):
        endpoint_uri = URIRef("https://prez.dev/endpoint/system/alt-profiles-listing")
        # runtime_values["selectedClass"] = prof_and_mt_info.selected_class

    # runtime_values["object"] = uri
    query_constructor = PrezQueryConstructor(
        runtime_values=runtime_values,
        endpoint_graph=endpoints_graph_cache,
        profile_graph=profiles_graph_cache,
        listing_or_object="object",
        focus_node=IRI(value=uri),
        endpoint_uri=endpoint_uri,
        profile_uri=pmts.selected["profile"],
    )
    query_constructor.generate_sparql()
    query = query_constructor.sparql

    try:
        if pmts.requested_mediatypes[0][0] == "application/sparql-query":
            return PlainTextResponse(query, media_type="application/sparql-query")
    except IndexError as e:
        log.debug(e.args[0])

    if pmts.selected["profile"] == URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"):
        item_graph, _ = await system_repo.send_queries([query], [])
    else:
        item_graph, _ = await repo.send_queries([query], [])
    if "anot+" in pmts.selected["mediatype"]:
        if not endpoint_uri == EP.object:
            await add_prez_links(item_graph, repo, endpoint_structure)
        await add_prez_links(item_graph, repo, endpoint_structure)
    return await return_from_graph(
        item_graph,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        pmts.selected["class"],
        repo,
    )
