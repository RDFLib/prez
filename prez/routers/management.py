from connegp import RDF_MEDIATYPES
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from prez.cache import tbox_cache
from prez.renderers.renderer import return_rdf

router = APIRouter(tags=["Management"])


@router.get("/purge-tbox-cache", summary="Purge Tbox Cache")
async def purge_tbox_cache():
    """Purges the Tbox cache"""
    tbox_cache.remove((None, None, None))
    return PlainTextResponse("Purged Tbox cache")


@router.get("/tbox-cache", summary="Show the Tbox Cache")
async def purge_tbox_cache(request: Request):
    """gets the mediatype from the request and returns the tbox cache in this mediatype"""
    mediatype = request.headers.get("Accept").split(",")[0]
    if not mediatype or mediatype not in RDF_MEDIATYPES:
        mediatype = "text/turtle"
    return await return_rdf(tbox_cache, mediatype, profile_headers={})
