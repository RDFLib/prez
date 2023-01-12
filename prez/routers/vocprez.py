from fastapi import APIRouter, Request
from rdflib import SKOS, URIRef

from models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.models.vocprez_item import VocabItem
from prez.models.vocprez_listings import VocabMembers
from prez.renderers.renderer import return_from_queries, return_profiles
from prez.services.sparql_queries import (
    generate_listing_construct_from_uri,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["VocPrez"])


@router.get("/v", summary="VocPrez Home")
@router.get("/v/profiles", summary="VocPrez Profiles")
async def vocprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by VocPrez"""
    vocprez_classes = frozenset([SKOS.Concept, SKOS.ConceptScheme, SKOS.Collection])
    return await return_profiles(vocprez_classes, "VocPrez", request)


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
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=vocprez_members.classes
    )
    vocprez_members.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(vocprez_members.selected_class),
            prez_type="SpacePrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    list_query = generate_listing_construct_from_uri(
        vocprez_members, prof_and_mt_info.profile, page, per_page
    )
    count_query = generate_listing_count_construct(vocprez_members)
    return await return_from_queries(
        [list_query, count_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "VocPrez",
    )


@router.get("/v/vocab/{scheme_id}", summary="Get ConceptScheme")
@router.get("/v/scheme/{scheme_id}", summary="Get ConceptScheme")
async def vocprez_scheme(request: Request, scheme_id: str):
    return await item_endpoint(request)


@router.get("/v/collection/{collection_id}", summary="Get Collection")
async def vocprez_collection(request: Request, collection_id: str):
    return await item_endpoint(request)


@router.get("/v/collection/{collection_id}/{concept_id}", summary="Get Concept")
@router.get("/v/scheme/{scheme_id}/{concept_id}", summary="Get Concept")
@router.get("/v/vocab/{scheme_id}/{concept_id}", summary="Get Concept")
async def item_endpoint(
    request: Request, scheme_or_collection_id: str = None, concept_id: str = None
):
    """Returns a VocPrez skos:Concept, Collection, Vocabulary, or ConceptScheme in the requested profile & mediatype"""
    vp_item = VocabItem(**request.path_params, url_path=str(request.url.path))
    prof_and_mt_info = ProfilesMediatypesInfo(request=request, classes=vp_item.classes)
    vp_item.selected_class = prof_and_mt_info.selected_class
    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(vp_item.selected_class),
            prez_type="SpacePrez",
            prof_and_mt_info=prof_and_mt_info,
        )
    item_query = generate_item_construct(vp_item, prof_and_mt_info.profile)
    item_members_query = generate_listing_construct_from_uri(
        vp_item, prof_and_mt_info.profile, 1, 5000
    )
    return await return_from_queries(
        [item_query, item_members_query],
        prof_and_mt_info.mediatype,
        prof_and_mt_info.profile,
        prof_and_mt_info.profile_headers,
        "VocPrez",
    )
