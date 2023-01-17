import asyncio
import io
from typing import Optional

from connegp import RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from fastapi.responses import StreamingResponse
from pydantic.types import List
from rdflib import Graph, URIRef, Namespace, Literal
from starlette.requests import Request
from starlette.responses import Response

from prez.models.profiles_item import ProfileItem
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.cache import profiles_graph_cache, tbox_cache
from prez.models import SpatialItem, VocabItem, CatalogItem
from prez.services.sparql_queries import (
    generate_item_construct,
    get_annotation_properties,
    get_annotation_predicates,
)
from prez.services.sparql_utils import sparql_construct


async def return_from_queries(
    queries: List[str], mediatype, profile, profile_headers, prez
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
    return await return_from_graph(graph, mediatype, profile, profile_headers, prez)


async def return_from_graph(graph, mediatype, profile, profile_headers, prez):
    if str(mediatype) in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype, profile_headers)

    # elif mediatype == "xml":
    #     ...

    else:
        if mediatype == Literal("text/anot+turtle"):
            return await return_annotated_rdf(graph, prez, profile_headers, profile)


async def return_rdf(graph, mediatype, profile_headers):
    RDF_SERIALIZER_TYPES_MAP["text/anot+turtle"] = "turtle"
    obj = io.BytesIO(
        graph.serialize(
            format=RDF_SERIALIZER_TYPES_MAP[str(mediatype)], encoding="utf-8"
        )
    )
    return StreamingResponse(content=obj, media_type=mediatype, headers=profile_headers)


async def return_annotated_rdf(graph, prez, profile_headers, profile):
    cache = tbox_cache
    profile_annotation_props = get_annotation_predicates(profile)
    queries_for_uncached, annotations_graph = await get_annotation_properties(
        graph, **profile_annotation_props
    )
    results = await sparql_construct(queries_for_uncached, prez)
    if results[1]:
        annotations_graph += results[1]
        cache += results[1]
    obj = io.BytesIO(
        (graph + annotations_graph).serialize(format="longturtle", encoding="utf-8")
    )
    return StreamingResponse(
        content=obj, media_type="text/turtle", headers=profile_headers
    )


async def return_profiles(
    classes: frozenset,
    prez_type: str,
    request: Optional[Request] = None,
    prof_and_mt_info: Optional = None,
) -> Response:
    prez_items = {
        "SpacePrez": SpatialItem,
        "VocPrez": VocabItem,
        "CatPrez": CatalogItem,
        "ProfilesPrez": ProfileItem,
    }
    if not prof_and_mt_info:
        prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=classes)
    if not request:
        request = prof_and_mt_info.request
    items = [
        prez_items[prez_type](uri=uri, url_path=str(request.url.path))
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


async def return_all__profiles():
    """
    returns all profiles the API knows about
    """
    pass
