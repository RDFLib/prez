import io
import json
import logging
from typing import Optional

from connegp import RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from rdflib import Graph, URIRef, Namespace, RDF
from starlette.requests import Request
from starlette.responses import Response

from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.profiles_item import ProfileItem
from prez.renderers.csv_renderer import render_csv_dropdown
from prez.renderers.json_renderer import render_json_dropdown, NotFoundError
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.methods import Repo
from prez.sparql.objects_listings import (
    generate_item_construct,
    get_annotation_properties,
)

log = logging.getLogger(__name__)


async def return_from_graph(
    graph,
    mediatype,
    profile,
    profile_headers,
    selected_class: URIRef,
    repo: Repo,
):
    profile_headers["Content-Disposition"] = "inline"

    if str(mediatype) in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype, profile_headers)

    elif profile == URIRef("https://w3id.org/profile/dd"):
        graph = await return_annotated_rdf(graph, profile, repo)

        try:
            # TODO: Currently, data is generated in memory, instead of in a streaming manner.
            #       Not possible to do a streaming response yet since we are reading the RDF
            #       data into an in-memory graph.
            jsonld_data = await render_json_dropdown(graph, profile, selected_class)

            if str(mediatype) == "text/csv":
                iri = graph.value(None, RDF.type, selected_class)
                if iri:
                    filename = get_curie_id_for_uri(URIRef(str(iri)))
                else:
                    filename = selected_class.split("#")[-1].split("/")[-1]
                stream = render_csv_dropdown(jsonld_data["@graph"])
                response = StreamingResponse(stream, media_type=mediatype)
                response.headers[
                    "Content-Disposition"
                ] = f"attachment;filename={filename}.csv"
                return response

            # application/json
            stream = io.StringIO(json.dumps(jsonld_data))
            return StreamingResponse(stream, media_type=mediatype)

        except NotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(err))

    else:
        if "anot+" in mediatype:
            non_anot_mediatype = mediatype.replace("anot+", "")
            graph = await return_annotated_rdf(graph, profile, repo)
            content = io.BytesIO(
                graph.serialize(format=non_anot_mediatype, encoding="utf-8")
            )
            return StreamingResponse(
                content=content, media_type=non_anot_mediatype, headers=profile_headers
            )

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unsupported mediatype: {mediatype}."
        )


async def return_rdf(graph, mediatype, profile_headers):
    RDF_SERIALIZER_TYPES_MAP["text/anot+turtle"] = "turtle"
    obj = io.BytesIO(
        graph.serialize(
            format=RDF_SERIALIZER_TYPES_MAP[str(mediatype)], encoding="utf-8"
        )
    )
    profile_headers["Content-Disposition"] = "inline"
    return StreamingResponse(content=obj, media_type=mediatype, headers=profile_headers)


async def get_annotations_graph(graph, cache, repo):
    queries_for_uncached, annotations_graph = await get_annotation_properties(graph)

    if queries_for_uncached is None:
        anots_from_triplestore = Graph()
    else:
        anots_from_triplestore, _ = await repo.send_queries([queries_for_uncached], [])

    if len(anots_from_triplestore) > 1:
        annotations_graph += anots_from_triplestore
        cache += anots_from_triplestore

    return annotations_graph


async def return_annotated_rdf(
    graph: Graph,
    profile,
    repo,
) -> Graph:
    from prez.cache import tbox_cache

    cache = tbox_cache
    queries_for_uncached, annotations_graph = await get_annotation_properties(graph)
    anots_from_triplestore, _ = await repo.send_queries([queries_for_uncached], [])
    if len(anots_from_triplestore) > 0:
        annotations_graph += anots_from_triplestore
        cache += anots_from_triplestore

    previous_triples_count = len(graph)

    # Expand the graph with annotations specified in the profile until no new statements are added.
    while True:
        graph += await get_annotations_graph(graph, cache, repo)
        if len(graph) == previous_triples_count:
            break
        previous_triples_count = len(graph)

    graph.bind("prez", "https://prez.dev/")
    return graph


async def return_profiles(
    classes: frozenset,
    repo: Repo,
    request: Optional[Request] = None,
    prof_and_mt_info: Optional[ProfilesMediatypesInfo] = None,
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
        prof_and_mt_info.selected_class,
        repo,
    )
