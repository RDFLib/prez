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
