from typing import Optional

from fastapi import APIRouter, Request
from rdflib import URIRef
from starlette.responses import PlainTextResponse

from prez.models.catprez_item import CatalogItem
from prez.models.catprez_listings import CatalogMembers
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.renderers.renderer import return_from_queries, return_profiles
from prez.sparql.objects_listings import (
    generate_listing_construct_from_uri,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["CatPrez"])


@router.get("/c", summary="CatPrez Home")
async def catprez_profiles():
    return PlainTextResponse("CatPrez Home")


@router.get("/c/catalogs", summary="List Catalogs")
async def catalogs_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of CatPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    catprez_members = CatalogMembers(url_path=str(request.url.path))
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=catprez_members.classes
    )
    catprez_members.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(catprez_members.selected_class),
            prez_type="SpacePrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    list_query, predicates_for_link_addition = generate_listing_construct_from_uri(
        catprez_members, prof_and_mt_info.profile, page, per_page
    )
    count_query = generate_listing_count_construct(catprez_members)
    return await return_from_queries(
        [list_query, count_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "CatPrez",
        predicates_for_link_addition,
    )


@router.get("/c/catalogs/{catalog_curie}/{resource_curie}", summary="Get Resource")
async def resource_endpoint(
    request: Request, catalog_curie: str = None, resource_curie: str = None
):
    return await item_endpoint(request)


@router.get("/c/catalogs/{catalog_curie}", summary="Get Catalog")
async def catalog_endpoint(request: Request, catalog_curie: str = None):
    return await item_endpoint(request)


async def item_endpoint(request: Request, cp_item: Optional[CatalogItem] = None):
    """Returns a CatPrez Catalog or Resource"""
    if not cp_item:
        cp_item = CatalogItem(
            **request.path_params,
            **request.query_params,
            url_path=str(request.url.path)
        )
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=cp_item.classes)
    cp_item.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(cp_item.selected_class),
            prez_type="SpacePrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    item_query = generate_item_construct(cp_item, prof_and_mt_info.profile)
    (
        item_members_query,
        predicates_for_link_addition,
    ) = generate_listing_construct_from_uri(cp_item, prof_and_mt_info.profile, 1, 20)
    return await return_from_queries(
        [item_query, item_members_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "CatPrez",
        predicates_for_link_addition,
    )
