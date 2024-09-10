import io
import json
import logging
from enum import Enum
from typing import Optional

from connegp import RDF_MEDIATYPES
from fastapi import APIRouter, Query
from rdflib import BNode, VANN
from rdflib import Graph, URIRef, Literal
from rdflib.collection import Collection
from starlette.requests import Request
from starlette.responses import PlainTextResponse, StreamingResponse

from prez.cache import endpoints_graph_cache, prefix_graph
from prez.cache import tbox_cache
from prez.config import settings
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_rdf
from prez.services.app_service import add_common_context_ontologies_to_tbox_cache

router = APIRouter(tags=["Management"])
log = logging.getLogger(__name__)


@router.get("/", summary="Home page", tags=["Prez"])
async def index():
    """Returns the following information about the API"""
    g = Graph()
    g.bind("prez", "https://prez.dev/")
    g.bind("ont", "https://prez.dev/ont/")
    g.add((URIRef(settings.system_uri), PREZ.version, Literal(settings.prez_version)))
    g += endpoints_graph_cache
    g += await return_annotation_predicates()
    log.info("Populated API info")
    return await return_rdf(g, "text/turtle", profile_headers={})


@router.get("/purge-tbox-cache", summary="Reset Tbox Cache")
async def purge_tbox_cache():
    """Purges the tbox cache, then re-adds annotations from common ontologies Prez has a copy of
    (reference_data/context_ontologies)."""
    tbox_cache.remove((None, None, None))
    await add_common_context_ontologies_to_tbox_cache()
    return PlainTextResponse("Tbox cache purged and reset to startup state")


@router.get("/tbox-cache", summary="Show the Tbox Cache")
async def return_tbox_cache(request: Request):
    """gets the mediatype from the request and returns the tbox cache in this mediatype"""
    mediatype = request.headers.get("Accept").split(",")[0]
    if not mediatype or mediatype not in RDF_MEDIATYPES:
        mediatype = "text/turtle"
    return await return_rdf(tbox_cache, mediatype, profile_headers={})


async def return_annotation_predicates():
    """
    Returns an RDF linked list of the annotation predicates used for labels, descriptions and provenance.
    """
    g = Graph()
    g.bind("prez", "https://prez.dev/")
    label_list_bn, description_list_bn, provenance_list_bn = BNode(), BNode(), BNode()
    g.add((PREZ.AnnotationPropertyList, PREZ.labelList, label_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.descriptionList, description_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.provenanceList, provenance_list_bn))
    Collection(g, label_list_bn, settings.label_predicates)
    Collection(g, description_list_bn, settings.description_predicates)
    Collection(g, provenance_list_bn, settings.provenance_predicates)
    return g


class PrefixMediatypesEnum(Enum):
    TEXT_TURTLE = "text/turtle"
    APPLICATION_JSON = "application/json"
    APPLICATION_LD_JSON = "application/ld+json"
    APPLICATION_RDF_XML = "application/rdf+xml"
    APPLICATION_N_TRIPLES = "application/n-triples"


@router.get("/prefixes", summary="Show prefixes known to prez")
async def show_prefixes(
        mediatype: Optional[PrefixMediatypesEnum] = Query(default=PrefixMediatypesEnum.TEXT_TURTLE, alias="_mediatype")
):
    """Returns the prefixes known to prez"""
    mediatype_str = str(mediatype.value)
    ns_map = {pfx: ns for pfx, ns in prefix_graph.namespaces()}
    if mediatype_str == "application/json":
        content = io.BytesIO(
            json.dumps(ns_map).encode("utf-8")
        )
    else:
        g = Graph()
        for prefix, namespace in ns_map.items():
            bn = BNode()
            g.add((bn, VANN.preferredNamespacePrefix, Literal(prefix)))
            g.add((bn, VANN.preferredNamespaceUri, Literal(namespace)))
        content = io.BytesIO(
            g.serialize(format=mediatype_str, encoding="utf-8")
        )
    return StreamingResponse(content=content, media_type=mediatype_str)
