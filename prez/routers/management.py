import logging

from connegp import RDF_MEDIATYPES
from fastapi import APIRouter
from rdflib import BNode
from rdflib import Graph, URIRef, Literal
from rdflib.collection import Collection
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from prez.services.annotations import process_term
from prez.cache import endpoints_graph_cache
from prez.cache import tbox_cache, tbox_cache_aio
from prez.config import settings
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_rdf
# from prez.services.app_service import add_common_context_ontologies_to_tbox_cache

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
    log.info(f"Populated API info")
    return await return_rdf(g, "text/turtle", profile_headers={})


@router.get("/purge-tbox-cache", summary="Reset Tbox Cache")
async def purge_tbox_cache():
    """Purges the tbox cache, then re-adds annotations from common ontologies Prez has a copy of
    (reference_data/context_ontologies)."""
    cache = process_term.cache
    cache_size = len(cache._cache)
    result = await cache.clear()
    if result:
        return PlainTextResponse(f"{cache_size} terms removed from tbox cache.")
    else:
        return PlainTextResponse("Tbox cache already empty.")


# @router.get("/tbox-cache", summary="Show the Tbox Cache")
# async def return_tbox_cache(request: Request):
#     """gets the mediatype from the request and returns the tbox cache in this mediatype"""
#     mediatype = request.headers.get("Accept").split(",")[0]
#     if not mediatype or mediatype not in RDF_MEDIATYPES:
#         mediatype = "text/turtle"
#     return await return_rdf(tbox_cache, mediatype, profile_headers={})


def unpack_cache():
    pass
    # #useful code for function
    # cache = process_term.cache
    # serialized_data = cache._cache[rdflib.term.URIRef('https://example.com/TopLevelCatalogTwo')]
    # deserialized_data = pickle.loads(serialized_data)
    # print(f"{' '.join([t.n3() for t in list(*b)])} .\n")


@router.get("/health")
async def health_check():
    return {"status": "ok"}


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
