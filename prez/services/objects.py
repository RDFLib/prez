import logging
from typing import Tuple

from fastapi import Request
from fastapi.responses import PlainTextResponse
from rdflib import URIRef

from prez.cache import endpoints_graph_cache, profiles_graph_cache
from prez.config import settings
from prez.reference_data.prez_ns import EP, ALTREXT
from prez.renderers.renderer import return_from_graph
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.link_generation import add_prez_links
from prez.services.query_generation.classes import get_classes
from prez.services.query_generation.umbrella import merge_listing_query_grammar_inputs, PrezQueryConstructorV2
from temp.grammar import IRI

log = logging.getLogger(__name__)


async def object_function_new(
        data_repo,
        system_repo,
        endpoint_structure,
        pmts,
        profile_nodeshape,
):
    profile_triples = profile_nodeshape.triples_list
    profile_gpnt = profile_nodeshape.gpnt_list
    query = PrezQueryConstructorV2(
        profile_triples=profile_triples,
        profile_gpnt=profile_gpnt
    ).to_string()

    if pmts.requested_mediatypes[0][0] == "application/sparql-query":
        return PlainTextResponse(query, media_type="application/sparql-query")

    item_graph, _ = await data_repo.send_queries([query], [])
    if "anot+" in pmts.selected["mediatype"]:
        await add_prez_links(item_graph, data_repo, endpoint_structure)
    return await return_from_graph(
        item_graph,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        pmts.selected["class"],
        data_repo,
        system_repo,
    )



async def object_function(
    request: Request,
    endpoint_uri: URIRef,
    uri: URIRef,
    request_url: str,
    repo: Repo,
    system_repo: Repo,
    endpoint_structure: Tuple[str] = settings.endpoint_structure,
):
    classes = await get_classes(uri=uri, repo=repo)
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=request.query_params,
        classes=classes,
        system_repo=system_repo,
    )
    await pmts.setup()

    # handle alternate profiles
    if pmts.selected["profile"] == ALTREXT["alt-profile"]:
        return await listing_function(
            request=request,
            repo=repo,
            system_repo=system_repo,
            endpoint_uri=endpoint_uri,
            hierarchy_level=1,
        )

    runtime_values = {}
    listing_or_object = "object"
    ns_gpnt = []
    ns_triples = []
    # query_constructor = PrezQueryConstructor(
    #     runtime_values=runtime_values,
    #     endpoint_graph=endpoints_graph_cache,
    #     profile_graph=profiles_graph_cache,
    #     listing_or_object=listing_or_object,
    #     focus_node=IRI(value=uri),
    #     endpoint_uri=endpoint_uri,
    #     profile_uri=pmts.selected["profile"],
    #     endpoint_shacl_triples=ns_triples,
    #     endpoint_shacl_gpnt=ns_gpnt,
    # )
    # query_constructor.generate_sparql()
    # query = query_constructor.sparql
    query = "to be removed"

    try:
        if pmts.requested_mediatypes[0][0] == "application/sparql-query":
            return PlainTextResponse(query, media_type="application/sparql-query")
    except IndexError as e:
        log.debug(e.args[0])

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
        system_repo,
    )
