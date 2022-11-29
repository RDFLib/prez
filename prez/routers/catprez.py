from fastapi import APIRouter, Request
from rdflib import DCTERMS

from prez.models.catprez_item import CatPrezItem
from prez.models.catprez_listings import CatPrezMembers
from prez.profiles.generate_profiles import get_profiles_and_mediatypes
from prez.renderers.renderer import return_data
from prez.services.connegp_service import get_requested_profile_and_mediatype
from prez.services.sparql_new import (
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
    (
        profile,
        mediatype,
        catprez_members.selected_class,
        profile_headers,
    ) = get_profiles_and_mediatypes(
        catprez_members.classes, req_profiles, req_mediatypes
    )
    list_query = generate_listing_construct(catprez_members, profile, page, per_page)
    count_query = generate_listing_count_construct(
        general_class=catprez_members.general_class
    )
    return await return_data(
        [list_query, count_query], mediatype, profile, profile_headers, "CatPrez"
    )


@router.get("/c/catalogs/{catalog_id}/{resource_id}", summary="Get Resource")
@router.get("/c/catalogs/{catalog_id}", summary="Get Catalog")
async def item_endpoint(
    request: Request, catalog_id: str = None, resource_id: str = None
):
    """Returns a CatPrez Catalog or Resource"""
    cp_item = CatPrezItem(**request.path_params, url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    (
        profile,
        mediatype,
        cp_item.selected_class,
        profile_headers,
    ) = get_profiles_and_mediatypes(cp_item.classes, req_profiles, req_mediatypes)
    item_query = generate_item_construct(cp_item, profile)
    item_members_query = generate_listing_construct(cp_item, profile, 1, 100)
    return await return_data(
        [item_query, item_members_query], mediatype, profile, profile_headers, "CatPrez"
    )


# @router.get("/c/profiles", summary="CatPrez Profiles")
# async def catprez_profiles(request: Request):
#     """Returns a JSON list of the profiles accepted by CatPrez"""
#     return await profiles_func(request, "CatPrez")
#
#
# @router.get("/conformance", summary="Conformance")
# async def conformance(request: Request):
#     """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
#     conformance_renderer = CatPrezConformanceRenderer(request)
#     return conformance_renderer.render()
