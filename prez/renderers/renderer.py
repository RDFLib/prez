import asyncio
import io

from connegp import RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from fastapi.responses import StreamingResponse
from rdflib import Literal, Graph

from prez.cache import tbox_cache
from prez.services.sparql_new import (
    get_annotation_properties,
    get_annotation_predicates,
)
from prez.services.sparql_utils import sparql_construct


async def return_from_queries(
    query_or_queries, mediatype, profile, profile_headers, prez
):
    # run the queries
    if isinstance(query_or_queries, list):
        # TODO union the queries and return respone directly - if the mediatype is RDF without annotations - or even if it is ?? annotations bit can be appended as well ??
        # probably still more performant to parse the graph and add the annotations in rdflib? or is parsing the graph the slow part?
        results = await asyncio.gather(
            *[sparql_construct(query, prez) for query in query_or_queries]
        )
        graph = Graph()
        for result in results:
            if result[0]:
                graph += result[1]
    else:
        _, graph = await sparql_construct(query_or_queries, prez)
    # return the data
    return await return_from_graph(graph, mediatype, profile, profile_headers, prez)


async def return_from_graph(graph, mediatype, profile, profile_headers, prez):
    if str(mediatype) in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype, profile_headers)

    # elif mediatype == "xml":
    #     ...

    else:
        if mediatype == Literal("text/html"):
            return await return_html(graph, prez, profile_headers, profile)


async def return_rdf(graph, mediatype, profile_headers):
    obj = io.BytesIO(
        graph.serialize(
            format=RDF_SERIALIZER_TYPES_MAP[str(mediatype)], encoding="utf-8"
        )
    )
    return StreamingResponse(content=obj, media_type=mediatype, headers=profile_headers)


async def return_html(graph, prez, profile_headers, profile):
    cache = tbox_cache
    profile_annotation_props = get_annotation_predicates(profile)
    queries_for_uncached, annotations_graph = await get_annotation_properties(
        graph, *profile_annotation_props
    )
    results = await sparql_construct(queries_for_uncached, prez)
    if results[1]:
        annotations_graph += results[1]
        cache += results[1]
    obj = io.BytesIO(
        (graph + annotations_graph).serialize(format="turtle", encoding="utf-8")
    )
    return StreamingResponse(
        content=obj, media_type="text/turtle", headers=profile_headers
    )
