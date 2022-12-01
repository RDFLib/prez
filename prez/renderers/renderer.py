import io

from fastapi.responses import StreamingResponse
import time

from rdflib import Literal
from starlette.responses import PlainTextResponse

from prez.services.spaceprez_service import *
from prez.services.spaceprez_service import sparql_construct
from prez.services.sparql_new import get_annotation_properties

from prez.cache import tbox_cache


async def return_data(query_or_queries, mediatype, profile, profile_headers, prez):
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
    if str(mediatype) in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype, profile_headers)

    # elif mediatype == "xml":
    #     ...

    else:
        if mediatype == Literal("text/html"):
            return await return_html(graph, prez, profile_headers)


async def return_rdf(graph, mediatype, profile_headers):
    obj = io.BytesIO(graph.serialize(format=mediatype, encoding="utf-8"))
    return StreamingResponse(content=obj, media_type=mediatype, headers=profile_headers)


async def return_html(graph, prez, profile_headers):
    cache = tbox_cache
    queries_for_uncached, labels_graph = await get_annotation_properties(graph)
    results = await sparql_construct(queries_for_uncached, prez)
    if results[1]:
        labels_graph += results[1]
        cache += results[1]
    obj = io.BytesIO(
        (graph + labels_graph).serialize(format="turtle", encoding="utf-8")
    )
    return StreamingResponse(
        content=obj, media_type="text/turtle", headers=profile_headers
    )
