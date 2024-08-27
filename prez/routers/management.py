import logging
import pickle

from aiocache import caches
from fastapi import APIRouter, Depends
from rdflib import BNode
from rdflib import Graph, URIRef, Literal
from rdflib.collection import Collection
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from prez.cache import endpoints_graph_cache
from prez.config import settings
from prez.dependencies import get_system_repo
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_rdf, return_from_graph
from prez.repositories import Repo
from prez.services.connegp_service import RDF_MEDIATYPES, NegotiatedPMTs

router = APIRouter(tags=["Management"])
log = logging.getLogger(__name__)


@router.get("/", summary="Home page", tags=["Prez"])
async def index(request: Request, system_repo: Repo = Depends(get_system_repo)):
    """Returns the following information about the API"""
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=request.query_params,
        classes=[PREZ.Object],
        system_repo=system_repo,
    )
    await pmts.setup()
    g = Graph()
    g.bind("prez", "https://prez.dev/")
    g.bind("ont", "https://prez.dev/ont/")
    g.add((URIRef(settings.system_uri), PREZ.version, Literal(settings.prez_version)))
    g += endpoints_graph_cache
    g += await return_annotation_predicates()
    return await return_from_graph(
        graph=g,
        mediatype=pmts.selected["mediatype"],
        profile=pmts.selected["profile"],
        profile_headers=pmts.generate_response_headers(),
        selected_class=pmts.selected["class"],
        repo=system_repo,
        system_repo=system_repo,
    )


@router.get("/purge-tbox-cache", summary="Reset Tbox Cache")
async def purge_tbox_cache():
    """Purges the tbox cache, then re-adds annotations from common ontologies Prez has a copy of
    (reference_data/annotations)."""
    cache = caches.get("default")
    cache_size = len(cache._cache)
    result = await cache.clear()
    if result and cache_size > 0:
        return PlainTextResponse(f"{cache_size} terms removed from tbox cache.")
    elif result and cache_size == 0:
        return PlainTextResponse("Tbox cache already empty.")
    elif not result:
        raise Exception("Internal Error: Tbox cache not purged.")


@router.get("/tbox-cache", summary="Show the Tbox Cache")
async def return_tbox_cache(request: Request):
    """gets the mediatype from the request and returns the tbox cache in this mediatype"""
    mediatype = request.headers.get("Accept").split(",")[0]
    if not mediatype or mediatype not in RDF_MEDIATYPES:
        mediatype = "text/turtle"
    cache = caches.get("default")
    cache_g = Graph()
    cache_dict = cache._cache
    for subject, pred_obj_bytes in cache_dict.items():
        # use pickle to deserialize the pred_obj_bytes
        pred_obj = pickle.loads(pred_obj_bytes)
        for pred, obj in pred_obj:
            if (
                pred_obj
            ):  # cache entry for a URI can be empty - i.e. no annotations found for URI
                # Add the expanded triple (subject, predicate, object) to 'annotations_g'
                cache_g.add((subject, pred, obj))
    return await return_rdf(cache_g, mediatype, profile_headers={})


@router.get("/health")
async def health_check():
    return {"status": "ok"}


async def return_annotation_predicates():
    """
    Returns an RDF linked list of the annotation predicates used for labels, descriptions and provenance.
    """
    g = Graph()
    g.bind("prez", "https://prez.dev/")
    label_list_bn, description_list_bn, provenance_list_bn, other_list_bn = (
        BNode(),
        BNode(),
        BNode(),
        BNode(),
    )
    g.add((PREZ.AnnotationPropertyList, PREZ.labelList, label_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.descriptionList, description_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.provenanceList, provenance_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.otherList, other_list_bn))
    Collection(g, label_list_bn, settings.label_predicates)
    Collection(g, description_list_bn, settings.description_predicates)
    Collection(g, provenance_list_bn, settings.provenance_predicates)
    Collection(g, other_list_bn, settings.other_predicates)
    return g
