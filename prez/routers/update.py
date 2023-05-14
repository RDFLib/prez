from fastapi import APIRouter
from fastapi import Request

from prez.sparql.methods import sparql_update

update_router = APIRouter(tags=["Update"])


@update_router.post("/c/update")
async def cp_update(request: Request):
    return await sparql_update(request, "CatPrez")


@update_router.post("/v/update")
async def vp_update(request: Request):
    return await sparql_update(request, "VocPrez")


@update_router.post("/s/update")
async def sp_update(request: Request):
    return await sparql_update(request, "SpacePrez")
