from fastapi import APIRouter, Request

from prez.models.vocprez_item import VocabItem
from prez.models.vocprez_listings import VocabMembers
from prez.profiles.generate_profiles import get_profiles_and_mediatypes, prez_profiles
from prez.renderers.renderer import return_from_queries
from prez.services.connegp_service import get_requested_profile_and_mediatype
from prez.services.sparql_new import (
    generate_listing_construct,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["VocPrez"])


@router.get("/v/collection", summary="List Collections")
@router.get("/v/scheme", summary="List ConceptSchemes")
@router.get("/v/vocab", summary="List Vocabularies")
async def schemes_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of VocPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    vocprez_members = VocabMembers(url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    (
        profile,
        mediatype,
        vocprez_members.selected_class,
        profile_headers,
        _,
    ) = get_profiles_and_mediatypes(
        vocprez_members.classes, req_profiles, req_mediatypes
    )
    list_query = generate_listing_construct(vocprez_members, profile, page, per_page)
    count_query = generate_listing_count_construct(vocprez_members)
    return await return_from_queries(
        [list_query, count_query], mediatype, profile, profile_headers, "VocPrez"
    )


@router.get("/v/vocab/{scheme_id}", summary="Get ConceptScheme")
@router.get("/v/scheme/{scheme_id}", summary="Get ConceptScheme")
async def vocprez_collection(request: Request, scheme_id: str):
    return await item_endpoint(request)


@router.get("/v/collection/{collection_id}", summary="Get Collection")
async def vocprez_collection(request: Request, collection_id: str):
    return await item_endpoint(request)


@router.get("/v/scheme/{scheme_id}/{concept_id}", summary="Get Concept")
@router.get("/v/vocab/{scheme_id}/{concept_id}", summary="Get Concept")
async def item_endpoint(
    request: Request, scheme_id: str = None, concept_id: str = None
):
    """Returns a VocPrez skos:Concept, Collection, Vocabulary, or ConceptScheme in the requested profile & mediatype"""
    vp_item = VocabItem(**request.path_params, url_path=str(request.url.path))
    req_profiles, req_mediatypes = get_requested_profile_and_mediatype(request)
    (
        profile,
        mediatype,
        vp_item.selected_class,
        profile_headers,
        _,
    ) = get_profiles_and_mediatypes(vp_item.classes, req_profiles, req_mediatypes)
    item_query = generate_item_construct(vp_item, profile)
    item_members_query = generate_listing_construct(vp_item, profile, 1, 100)
    return await return_from_queries(
        [item_query, item_members_query], mediatype, profile, profile_headers, "VocPrez"
    )


@router.get(
    "/v/profiles",
    summary="VocPrez Profiles",
)
async def vocprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by VocPrez"""
    return await prez_profiles(request, "VocPrez")
