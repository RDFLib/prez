import io

from fastapi.responses import StreamingResponse
import time
from prez.services.spaceprez_service import *
from prez.services.spaceprez_service import sparql_construct
from prez.services.sparql_new import get_annotation_properties

from prez.cache import tbox_cache


async def return_data(query_or_queries, mediatype, profile, prez):
    # run the queries
    if isinstance(query_or_queries, list):
        results = await asyncio.gather(
            *[sparql_construct(query, prez) for query in query_or_queries]
        )
        graph = Graph()
        for result in results:
            graph += result[1]
    else:
        _, graph = await sparql_construct(query_or_queries, prez)

    # return the data
    if mediatype in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype)

    # elif mediatype == "xml":
    #     ...

    else:
        if mediatype == "text/html":
            return await return_html(graph, prez)


async def return_rdf(graph, mediatype):
    obj = io.BytesIO(graph.serialize(format=mediatype, encoding="utf-8"))
    return StreamingResponse(content=obj, media_type=mediatype)


async def return_html(graph, prez):
    cache = tbox_cache
    queries_for_uncached, labels_graph = await get_annotation_properties(graph)
    results = await sparql_construct(queries_for_uncached, prez)
    if results[1]:
        labels_graph += results[1]
        cache += results[1]
    obj = io.BytesIO(
        (graph + labels_graph).serialize(format="turtle", encoding="utf-8")
    )
    return StreamingResponse(content=obj, media_type="text/turtle")
