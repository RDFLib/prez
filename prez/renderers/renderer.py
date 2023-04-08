import asyncio
import io
import logging
from typing import Optional, Dict

from connegp import RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from fastapi.responses import StreamingResponse
from pydantic.types import List
from rdflib import Graph, URIRef, Namespace, Literal
from starlette.requests import Request
from starlette.responses import Response

from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.profiles_item import ProfileItem
from prez.reference_data.prez_ns import PREZ
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.objects_listings import (
    generate_item_construct,
    get_annotation_properties,
    get_annotation_predicates,
)
from prez.sparql.methods import sparql_construct


log = logging.getLogger(__name__)


async def return_from_queries(
    queries: List[str], mediatype, profile, profile_headers, prez, predicates_for_link_addition: Dict = {}
):
    """
    Executes SPARQL queries, loads these to RDFLib Graphs, and calls the "return_from_graph" function to return the
    content
    """
    results = await asyncio.gather(
        *[sparql_construct(query, prez) for query in queries]
    )
    graphs = [result[1] for result in results if result[0]]
    graph = graphs[0]
    if len(graphs) > 1:
        for g in graphs[1:]:
            graph.__iadd__(g)
    return await return_from_graph(graph, mediatype, profile, profile_headers, prez, predicates_for_link_addition)


async def return_from_graph(graph, mediatype, profile, profile_headers, prez, predicates_for_link_addition: dict = {}):
    profile_headers["Content-Disposition"] = "inline"
    if str(mediatype) in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype, profile_headers)

    # elif mediatype == "xml":
    #     ...

    else:
        if mediatype == Literal("text/anot+turtle"):
            return await return_annotated_rdf(graph, prez, profile_headers, profile, predicates_for_link_addition)


async def return_rdf(graph, mediatype, profile_headers):
    RDF_SERIALIZER_TYPES_MAP["text/anot+turtle"] = "turtle"
    obj = io.BytesIO(
        graph.serialize(
            format=RDF_SERIALIZER_TYPES_MAP[str(mediatype)], encoding="utf-8"
        )
    )
    profile_headers["Content-Disposition"] = "inline"
    return StreamingResponse(content=obj, media_type=mediatype, headers=profile_headers)


async def return_annotated_rdf(graph, prez, profile_headers, profile, predicates_for_link_addition):
    from prez.cache import tbox_cache

    cache = tbox_cache
    profile_annotation_props = get_annotation_predicates(profile)
    queries_for_uncached, annotations_graph = await get_annotation_properties(
        graph, **profile_annotation_props
    )
    results = await sparql_construct(queries_for_uncached, prez)
    if results[1]:
        annotations_graph += results[1]
        cache += results[1]

    generate_prez_links(graph, predicates_for_link_addition)

    obj = io.BytesIO(
        (graph + annotations_graph).serialize(format="text/turtle", encoding="utf-8")
    )
    return StreamingResponse(
        content=obj, media_type="text/turtle", headers=profile_headers
    )


def generate_prez_links(graph, predicates_for_link_addition):
    if not predicates_for_link_addition:
        return
    if predicates_for_link_addition["link_constructor"].endswith("/object?uri="):
        generate_object_endpoint_link(graph, predicates_for_link_addition)
    else:
        if predicates_for_link_addition["ob_chi"]:
            triples_for_links = graph.triples_choices((None, predicates_for_link_addition["ob_chi"], None))
            for triple in triples_for_links:
                graph.add((triple[2], PREZ.link, Literal(predicates_for_link_addition["link_constructor"] + f"/{get_curie_id_for_uri(triple[2])}")))
        if predicates_for_link_addition["ib_chi"]:
            for triple in graph.triples_choices((None, predicates_for_link_addition["ib_chi"], None)):
                graph.add((triple[2], PREZ.link, Literal(predicates_for_link_addition["link_constructor"])))
        if predicates_for_link_addition["ob_par"]:
            triples_for_links = graph.triples_choices((None, predicates_for_link_addition["ob_par"], None))
            new_link_constructor = '/'.join(predicates_for_link_addition["link_constructor"].split('/')[:-1])
            for triple in triples_for_links:
                graph.add((triple[2], PREZ.link, Literal(new_link_constructor + f"/{get_curie_id_for_uri(triple[2])}")))
        if predicates_for_link_addition["ib_par"]:
            triples_for_links = graph.triples_choices((None, predicates_for_link_addition["ib_par"], None))
            new_link_constructor = '/'.join(predicates_for_link_addition["link_constructor"].split('/')[:-1])
            for triple in triples_for_links:
                graph.add((triple[2], PREZ.link, Literal(new_link_constructor + f"/{get_curie_id_for_uri(triple[2])}")))


def generate_object_endpoint_link(graph, predicates_for_link_addition):
    all_preds = predicates_for_link_addition["child"] + predicates_for_link_addition["parent"]
    objects_for_links = graph.triples_choices((None, all_preds, None))
    for o in objects_for_links:
        graph.add((o[2], PREZ.link, Literal(f"{predicates_for_link_addition['link_constructor']}{o[2]}")))


async def return_profiles(
    classes: frozenset,
    prez_type: str,
    request: Optional[Request] = None,
    prof_and_mt_info: Optional = None,
) -> Response:
    from prez.cache import profiles_graph_cache

    if not prof_and_mt_info:
        prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=classes)
    if not request:
        request = prof_and_mt_info.request
    items = [
        ProfileItem(uri=str(uri), url_path=str(request.url.path))
        for uri in prof_and_mt_info.avail_profile_uris
    ]
    queries = [
        generate_item_construct(profile, URIRef("http://kurrawong.net/profile/prez"))
        for profile in items
    ]
    g = Graph(bind_namespaces="rdflib")
    g.bind("altr-ext", Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#"))
    for q in queries:
        g += profiles_graph_cache.query(q)
    return await return_from_graph(
        g,
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        prez_type,
    )
