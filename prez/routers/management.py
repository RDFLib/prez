from connegp import RDF_MEDIATYPES
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from prez.cache import tbox_cache
from prez.renderers.renderer import return_rdf
from prez.services.app_service import add_common_context_ontologies_to_tbox_cache

router = APIRouter(tags=["Management"])


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
