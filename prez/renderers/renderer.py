import asyncio
import io

from connegp import RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from fastapi.responses import StreamingResponse
from pydantic.types import List
from rdflib import Literal

from prez.cache import tbox_cache
from prez.services.sparql_queries import (
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
    graph = results[0][1]
    if len(results) > 1:
        for result in results[1:]:
            graph.__iadd__(result[1])
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
