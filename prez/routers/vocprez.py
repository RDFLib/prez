import os

from async_lru import alru_cache
from fastapi import APIRouter, Request

from prez.models.vocprez_item import VocabItem
from prez.models.vocprez_listings import VocPrezMembers

from prez.routers.spaceprez import connegp_placeholder, return_data
from prez.services.sparql_new import (
    generate_listing_construct,
    generate_listing_count_construct,
    generate_item_construct,
)
from prez.services.vocprez_service import *

ENABLED_PREZS = os.getenv("ENABLED_PREZS").split("|")

router = APIRouter(tags=["VocPrez"])


@router.get("/collection", summary="List Collections")
@router.get("/scheme", summary="List ConceptSchemes")
@router.get("/vocab", summary="List Vocabularies")
async def schemes_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of VocPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    vocprez_members = VocPrezMembers(url=str(request.url.path))
    profile, mediatype = connegp_placeholder(
        request, vocprez_members.children_general_class
    )
    list_query = generate_listing_construct(vocprez_members, page, per_page, profile)
    count_query = generate_listing_count_construct(
        general_class=vocprez_members.children_general_class
    )
    return await return_data([list_query, count_query], mediatype, profile, "VocPrez")


@router.get("/vocab/{scheme_id}", summary="Get ConceptScheme")
@router.get("/scheme/{scheme_id}", summary="Get ConceptScheme")
async def vocprez_collection(request: Request, scheme_id: str):
    return await item_endpoint(request)


@router.get("/collection/{collection_id}", summary="Get Collection")
async def vocprez_collection(request: Request, collection_id: str):
    return await item_endpoint(request)


@router.get("/scheme/{scheme_id}/{concept_id}", summary="Get Concept")
@router.get("/vocab/{scheme_id}/{concept_id}", summary="Get Concept")
async def item_endpoint(
    request: Request, scheme_id: str = None, concept_id: str = None
):
    """Returns a VocPrez skos:Concept, Collection, Vocabulary, or ConceptScheme in the requested profile & mediatype"""
    vp_item = VocabItem(**request.path_params, url=str(request.url.path))
    profile, mediatype = connegp_placeholder(request, vp_item.general_class)
    ### TODO - remove temporary hardcoding of profile - profile will be determined in a connegp like manner
    profile = {"uri": URIRef("https://w3id.org/profile/vocpub")}
    ###
    query = generate_item_construct(vp_item, profile)
    print(query)
    return await return_data(query, mediatype, profile, "VocPrez")


@router.get(
    "/vocprez-profiles",
    summary="VocPrez Profiles",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def vocprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by VocPrez"""
    return await profiles_func(request, "VocPrez")
