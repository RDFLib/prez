import os

from fastapi import APIRouter
from starlette.responses import PlainTextResponse

from prez.cache import tbox_cache

router = APIRouter(tags=["Management"])


@router.get("/purge-tbox-cache", summary="Purge Tbox Cache")
async def purge_tbox_cache():
    """Purges the Tbox cache"""
    tbox_cache.remove((None, None, None))
    os.unlink("../tbox_cache.ttl")
    return PlainTextResponse("Purged Tbox cache")
