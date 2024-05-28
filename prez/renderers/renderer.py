import io
import json
import logging
import time

from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from rdflib import Graph, URIRef, RDF

from prez.cache import prefix_graph
from prez.renderers.csv_renderer import render_csv_dropdown
from prez.renderers.json_renderer import render_json_dropdown, NotFoundError
from prez.repositories import Repo
from prez.services.annotations import (
    get_annotation_properties,
)
from prez.services.connegp_service import RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from prez.services.curie_functions import get_curie_id_for_uri

log = logging.getLogger(__name__)


async def return_from_graph(
    graph,
    mediatype,
    profile,
    profile_headers,
    selected_class: URIRef,
    repo: Repo,
    system_repo: Repo,
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
                response.headers["Content-Disposition"] = (
                    f"attachment;filename={filename}.csv"
                )
                return response

            # application/json
            stream = io.StringIO(json.dumps(jsonld_data))
            return StreamingResponse(stream, media_type=mediatype)

        except NotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(err))

    else:
        if "anot+" in mediatype:
            non_anot_mediatype = mediatype.replace("anot+", "")
            graph = await return_annotated_rdf(graph, repo, system_repo)
            graph.namespace_manager = prefix_graph.namespace_manager
            content = io.BytesIO(
                graph.serialize(format=non_anot_mediatype, encoding="utf-8")
            )
            return StreamingResponse(
                content=content, media_type=non_anot_mediatype, headers=profile_headers
            )

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unsupported mediatype: {mediatype}."
        )


async def return_rdf(graph: Graph, mediatype, profile_headers):
    RDF_SERIALIZER_TYPES_MAP["text/anot+turtle"] = "turtle"
    obj = io.BytesIO(
        graph.serialize(
            format=RDF_SERIALIZER_TYPES_MAP[str(mediatype)], encoding="utf-8"
        )
    )
    profile_headers["Content-Disposition"] = "inline"
    return StreamingResponse(content=obj, media_type=mediatype, headers=profile_headers)


async def return_annotated_rdf(
    graph: Graph,
    repo: Repo,
    system_repo: Repo,
) -> Graph:
    t_start = time.time()
    annotations_graph = await get_annotation_properties(graph, repo, system_repo)
    # get annotations for annotations - no need to do this recursively
    annotations_graph += await get_annotation_properties(
        annotations_graph, repo, system_repo
    )
    log.debug(f"Time to get annotations: {time.time() - t_start}")
    return graph.__iadd__(annotations_graph)
