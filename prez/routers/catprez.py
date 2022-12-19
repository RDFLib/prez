from fastapi import APIRouter, Request

from prez.models.catprez_item import CatalogItem
from prez.models.catprez_listings import CatalogMembers
from prez.profiles.generate_profiles import get_profiles_and_mediatypes, prez_profiles
from prez.renderers.renderer import return_from_queries
from prez.services.connegp_service import get_requested_profile_and_mediatype
from prez.services.sparql_queries import (
    generate_listing_construct_from_uri,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["CatPrez"])


@router.get("/c", summary="CatPrez Home")
async def catprez_home(request: Request):
    return await prez_profiles(request, "CatPrez")


@router.get("/c/catalogs", summary="List Catalogs")
async def catalogs_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of CatPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    catprez_members = CatalogMembers(url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    (
        profile,
        mediatype,
        catprez_members.selected_class,
        profile_headers,
        _,
    ) = get_profiles_and_mediatypes(
        catprez_members.classes, req_profiles, req_mediatypes
    )
    list_query = generate_listing_construct_from_uri(
        catprez_members, profile, page, per_page
    )
    count_query = generate_listing_count_construct(catprez_members)
    return await return_from_queries(
        [list_query, count_query], mediatype, profile, profile_headers, "CatPrez"
    )


@router.get("/c/catalogs/{catalog_id}/{resource_id}", summary="Get Resource")
@router.get("/c/catalogs/{catalog_id}", summary="Get Catalog")
async def item_endpoint(
    request: Request, catalog_id: str = None, resource_id: str = None
):
    """Returns a CatPrez Catalog or Resource"""
    cp_item = CatalogItem(**request.path_params, url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    (
        profile,
        mediatype,
        cp_item.selected_class,
        profile_headers,
        _,
    ) = get_profiles_and_mediatypes(cp_item.classes, req_profiles, req_mediatypes)
    item_query = generate_item_construct(cp_item, profile)
    item_members_query = generate_listing_construct_from_uri(cp_item, profile, 1, 100)
    return await return_from_queries(
        [item_query, item_members_query], mediatype, profile, profile_headers, "CatPrez"
    )


@router.get("/c/profiles", summary="CatPrez Profiles")
async def catprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by CatPrez"""
    return await prez_profiles(request, "CatPrez")


#
#
# @router.get("/conformance", summary="Conformance")
# async def conformance(request: Request):
#     """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
#     conformance_renderer = CatPrezConformanceRenderer(request)
#     return conformance_renderer.render()
