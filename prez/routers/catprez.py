from fastapi import APIRouter, Request

from models.catprez_item import CatprezItem
from models.catprez_listings import CatPrezMembers
from prez.profiles.generate_profiles import get_profile_and_mediatype
from renderers.renderer import return_data
from services.connegp_service import get_requested_profile_and_mediatype
from services.sparql_new import (
    generate_listing_construct,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["CatPrez"])


@router.get("/c/catalogs", summary="List Catalogs")
async def catalogs_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of CatPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    catprez_members = CatPrezMembers(url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    profile, mediatype = get_profile_and_mediatype(
        catprez_members.classes, req_profiles, req_mediatypes
    )
    list_query = generate_listing_construct(catprez_members, page, per_page)
    count_query = generate_listing_count_construct(
        general_class=catprez_members.general_class
    )
    return await return_data([list_query, count_query], mediatype, profile, "CatPrez")


@router.get("/c/catalog/{catalog_id}/{resource_id}", summary="Get Resource")
@router.get("/c/catalogs/{catalog_id}", summary="Get Catalog")
async def item_endpoint(
    request: Request, catalog_id: str = None, resource_id: str = None
):
    """Returns a CatPrez Catalog or Resource"""
    cp_item = CatprezItem(**request.path_params, url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    profile, mediatype = get_profile_and_mediatype(
        cp_item.classes, req_profiles, req_mediatypes
    )
    query = generate_item_construct(cp_item, profile)
    print(query)
    return await return_data(query, mediatype, profile, "CatPrez")


@router.get("/c/profiles", summary="CatPrez Profiles")
async def catprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by CatPrez"""
    return await profiles_func(request, "CatPrez")


@router.get("/conformance", summary="Conformance")
async def conformance(request: Request):
    """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
    conformance_renderer = CatPrezConformanceRenderer(request)
    return conformance_renderer.render()
