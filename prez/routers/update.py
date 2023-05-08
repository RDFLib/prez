import logging

from fastapi import APIRouter
from fastapi import Request

from prez.sparql.methods import sparql_update

logger = logging.getLogger(__name__)
update_router = APIRouter(tags=["Update"])


async def forward_request_to_backend(request: Request, prez):
    return await sparql_update(request, prez)


@update_router.post("/c/update")
async def your_endpoint(request: Request):
    return await forward_request_to_backend(request, "CatPrez")


@update_router.post("/v/update")
async def your_endpoint(request: Request):
    return await forward_request_to_backend(request, "VocPrez")


@update_router.post("/s/update")
async def your_endpoint(request: Request):
    return await forward_request_to_backend(request, "SpacePrez")
