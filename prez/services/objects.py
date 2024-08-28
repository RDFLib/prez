import io
import logging
import time

from fastapi.responses import PlainTextResponse
from sparql_grammar_pydantic import TriplesSameSubject, IRI, Var, TriplesSameSubjectPath
from starlette.responses import StreamingResponse

from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import ALTREXT, ONT
from prez.renderers.renderer import return_from_graph
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.link_generation import add_prez_links
from prez.services.listings import listing_function
from prez.services.query_generation.umbrella import (
    PrezQueryConstructor,
)

log = logging.getLogger(__name__)


async def object_function(
        data_repo,
        system_repo,
        endpoint_structure,
        pmts,
        profile_nodeshape,
):
    if pmts.selected["profile"] == ALTREXT["alt-profile"]:
        none_keys = [
            "endpoint_nodeshape",
            "concept_hierarchy_query",
            "cql_parser",
            "search_query",
        ]
        none_kwargs = {key: None for key in none_keys}
        query_params = QueryParams(
            mediatype=pmts.selected["mediatype"],
            filter=None,
            q=None,
            page=1,
            per_page=100,
            order_by=None,
            order_by_direction=None,
        )
        return await listing_function(
            data_repo=data_repo,
            system_repo=system_repo,
            endpoint_structure=endpoint_structure,
            pmts=pmts,
            profile_nodeshape=profile_nodeshape,
            query_params=query_params,
            original_endpoint_type=ONT["ObjectEndpoint"],
            **none_kwargs,
        )
    if "anot+" in pmts.selected["mediatype"]:
        profile_nodeshape.tss_list.append(
            TriplesSameSubject.from_spo(
                subject=profile_nodeshape.focus_node,
                predicate=IRI(value="https://prez.dev/type"),
                object=IRI(value="https://prez.dev/FocusNode"),
            )
        )
    query = PrezQueryConstructor(
        profile_triples=profile_nodeshape.tssp_list,
        profile_gpnt=profile_nodeshape.gpnt_list,
        construct_tss_list=profile_nodeshape.tss_list,
    ).to_string()

    if pmts.requested_mediatypes[0][0] == "application/sparql-query":
        return PlainTextResponse(query, media_type="application/sparql-query")
    query_start_time = time.time()
    item_graph, _ = await data_repo.send_queries([query], [])
    log.debug(f"Query time: {time.time() - query_start_time}")
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


async def ogc_features_object_function(
        collectionId,
        itemId,
        props,
        data_repo,
):
    if itemId is not None:
        focus_node_curie = itemId
    else:
        focus_node_curie = collectionId
    focus_node_uri = await get_uri_for_curie_id(focus_node_curie)
    focus_node = IRI(value=focus_node_uri)
    if not props:
        prop_terms = [Var(value="props")]  # get all props
    else:
        prop_terms = [IRI(value=prop) for prop in props]  # get specific props
    tssp_list = []
    for i, prop in enumerate(prop_terms):
        tssp_list.append(
            TriplesSameSubjectPath.from_spo(
                subject=focus_node,
                predicate=prop,
                object=Var(value=f"var_{i}"),
            )
        )
    query = PrezQueryConstructor(
        profile_triples=tssp_list,
    ).to_string()

    query_start_time = time.time()
    item_graph, _ = await data_repo.send_queries([query], [])
    log.debug(f"Query time: {time.time() - query_start_time}")
    link_headers = None
    content = io.BytesIO(
        item_graph.serialize(format="turtle", encoding="utf-8")
    )
    return content, link_headers
