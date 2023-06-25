import io
import logging
from typing import Optional, Dict

from connegp import RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from fastapi.responses import StreamingResponse
from pydantic.types import List
from rdflib import Graph, URIRef, Namespace, Literal, RDF
from starlette.requests import Request
from starlette.responses import Response

from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.profiles_item import ProfileItem
from prez.reference_data.prez_ns import PREZ
from prez.sparql.methods import send_queries
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.objects_listings import (
    generate_item_construct,
    get_annotation_properties,
    get_annotation_predicates,
)

log = logging.getLogger(__name__)


async def return_from_queries(
    queries: List[str],
    mediatype,
    profile,
    profile_headers,
    predicates_for_link_addition: dict = None,
):
    """
    Executes SPARQL queries, loads these to RDFLib Graphs, and calls the "return_from_graph" function to return the
    content
    """
    graph, _ = await send_queries(queries)
    return await return_from_graph(
        graph, mediatype, profile, profile_headers, predicates_for_link_addition
    )


async def return_from_graph(
    graph,
    mediatype,
    profile,
    profile_headers,
    predicates_for_link_addition: dict = None,
):
    profile_headers["Content-Disposition"] = "inline"
    if str(mediatype) in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype, profile_headers)

    # elif mediatype == "xml":
    #     ...

    else:
        if "anot+" in mediatype:
            return await return_annotated_rdf(
                graph, profile_headers, profile, predicates_for_link_addition, mediatype
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


async def get_annotations_graph(profile, graph, cache):
    profile_annotation_props = get_annotation_predicates(profile)
    queries_for_uncached, annotations_graph = await get_annotation_properties(
        graph, **profile_annotation_props
    )

    if queries_for_uncached is None:
        anots_from_triplestore = Graph()
    else:
        anots_from_triplestore = await queries_to_graph([queries_for_uncached])

    if len(anots_from_triplestore) > 1:
        annotations_graph += anots_from_triplestore
        cache += anots_from_triplestore

    return annotations_graph


async def return_annotated_rdf(
    graph: Graph,
    profile_headers,
    profile,
    predicates_for_link_addition: dict,
    mediatype="text/anot+turtle",
):
    from prez.cache import tbox_cache

    non_anot_mediatype = mediatype.replace("anot+", "")

    cache = tbox_cache
    profile_annotation_props = get_annotation_predicates(profile)
    queries_for_uncached, annotations_graph = await get_annotation_properties(
        graph, **profile_annotation_props
    )
    anots_from_triplestore, _ = await send_queries([queries_for_uncached])
    if len(anots_from_triplestore) > 1:
        annotations_graph += anots_from_triplestore
        cache += anots_from_triplestore

    previous_triples_count = len(graph)

    # Expand the graph with annotations specified in the profile until no new statements are added.
    while True:
        graph += await get_annotations_graph(profile, graph, cache)
        if len(graph) == previous_triples_count:
            break
        previous_triples_count = len(graph)

    generate_prez_links(graph, predicates_for_link_addition)

    obj = io.BytesIO(graph.serialize(format=non_anot_mediatype, encoding="utf-8"))
    return StreamingResponse(
        content=obj, media_type=non_anot_mediatype, headers=profile_headers
    )


def generate_prez_links(graph, predicates_for_link_addition):
    if not predicates_for_link_addition:
        return
    if predicates_for_link_addition["link_constructor"].endswith("/object?uri="):
        generate_object_endpoint_link(graph, predicates_for_link_addition)
    else:
        if predicates_for_link_addition["focus_to_child"]:
            triples_for_links = graph.triples_choices(
                (None, predicates_for_link_addition["focus_to_child"], None)
            )
            for triple in triples_for_links:
                graph.add(
                    (
                        triple[2],
                        PREZ.link,
                        Literal(
                            predicates_for_link_addition["link_constructor"]
                            + f"/{get_curie_id_for_uri(triple[2])}"
                        ),
                    )
                )
        if predicates_for_link_addition["child_to_focus"]:
            for triple in graph.triples_choices(
                (None, predicates_for_link_addition["child_to_focus"], None)
            ):
                graph.add(
                    (
                        triple[0],
                        PREZ.link,
                        Literal(
                            predicates_for_link_addition["link_constructor"]
                            + f"/{get_curie_id_for_uri(triple[0])}"
                        ),
                    )
                )
        if predicates_for_link_addition["focus_to_parent"]:
            triples_for_links = graph.triples_choices(
                (None, predicates_for_link_addition["focus_to_parent"], None)
            )
            new_link_constructor = "/".join(
                predicates_for_link_addition["link_constructor"].split("/")[:-1]
            )
            for triple in triples_for_links:
                graph.add(
                    (
                        triple[2],
                        PREZ.link,
                        Literal(
                            new_link_constructor + f"/{get_curie_id_for_uri(triple[2])}"
                        ),
                    )
                )
        if predicates_for_link_addition["parent_to_focus"]:
            triples_for_links = graph.triples_choices(
                (None, predicates_for_link_addition["parent_to_focus"], None)
            )
            new_link_constructor = "/".join(
                predicates_for_link_addition["link_constructor"].split("/")[:-1]
            )
            for triple in triples_for_links:
                graph.add(
                    (
                        triple[2],
                        PREZ.link,
                        Literal(
                            new_link_constructor + f"/{get_curie_id_for_uri(triple[2])}"
                        ),
                    )
                )
        if predicates_for_link_addition["top_level_gen_class"]:
            instances = graph.subjects(
                predicate=RDF.type,
                object=predicates_for_link_addition["top_level_gen_class"],
            )
            for instance in instances:
                graph.add(
                    (
                        instance,
                        PREZ.link,
                        Literal(
                            predicates_for_link_addition["link_constructor"]
                            + f"/{get_curie_id_for_uri(instance)}"
                        ),
                    )
                )


def generate_object_endpoint_link(graph, predicates_for_link_addition):
    all_preds = (
        predicates_for_link_addition["parent_to_focus"]
        + predicates_for_link_addition["focus_to_parent"]
        + predicates_for_link_addition["child_to_focus"]
        + predicates_for_link_addition["focus_to_child"]
    )
    objects_for_links = graph.triples_choices((None, all_preds, None))
    for o in objects_for_links:
        graph.add(
            (
                o[2],
                PREZ.link,
                Literal(f"{predicates_for_link_addition['link_constructor']}{o[2]}"),
            )
        )


async def return_profiles(
    classes: frozenset,
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
    )
