from typing import Optional

from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse

from prez.routers.object import listing_function, item_function

router = APIRouter(tags=["CatPrez"])


@router.get("/c", summary="CatPrez Home")
async def catprez_profiles():
    return PlainTextResponse("CatPrez Home")


@router.get(
    "/c/catalogs",
    summary="List Catalogs",
    name="https://prez.dev/endpoint/catprez/catalog-listing",
)
async def catalog_list(
    request: Request, page: Optional[int] = 1, per_page: Optional[int] = 20
):
    return await listing_function(request, page, per_page)


@router.get(
    "/c/catalogs/{catalog_curie}/{resource_curie}",
    summary="Get Resource",
    name="https://prez.dev/endpoint/catprez/resource",
)
async def resource_item(request: Request, catalog_curie: str, resource_curie: str):
    return await item_function(request, object_curie=resource_curie)


@router.get(
    "/c/catalogs/{catalog_curie}",
    summary="Get Catalog",
    name="https://prez.dev/endpoint/catprez/catalog",
)
async def catalog_item(request: Request, catalog_curie: str):
    return await item_function(request, object_curie=catalog_curie)
