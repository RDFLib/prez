import io

from async_lru import alru_cache
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import StreamingResponse

from prez.models.vocprez import *
from prez.profiles.generate_profiles import (
    build_alt_graph,
)
from prez.renderers.vocprez import *
from prez.services.vocprez_service import *
from prez.utils import templates
from prez.view_funcs import profiles_func
from prez.routers.spaceprez_router import connegp_placeholder, return_data
from prez.models.vocprez.vocprez_listings import VocPrezMembers
from prez.models.vocprez.vocprez_item import VocPrezItem
from prez.services.sparql_new import (
    generate_listing_construct,
    generate_listing_count_construct,
    generate_item_construct,
)

router = APIRouter(tags=["VocPrez"] if len(ENABLED_PREZS) > 1 else [])


@alru_cache(maxsize=5)
@router.get(
    "/vocprez", summary="VocPrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def vocprez_home_endpoint(request: Request):
    """Returns a VocPrez dcat:Dataset in the necessary profile & mediatype"""
    return await home(request)


async def home(request: Request):
    """Returns the VocPrez home page in the necessary profile & mediatype"""
    home_renderer = VocPrezDatasetRenderer(request)
    if home_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            PREZ.VocPrezHome,
            home_renderer.profile_details.profiles_formats,
            home_renderer.profile_details.available_profiles_dict,
        )
        return home_renderer.render(alt_profiles_graph=alt_profiles_graph)
    sparql_result = await get_dataset_construct()
    dataset = VocPrezDataset(sparql_result)
    home_renderer.set_dataset(dataset)
    return home_renderer.render()


async def about(request: Request):
    return templates.TemplateResponse(
        "vocprez/vocprez_about.html", {"request": request}
    )


@router.get(
    "/vocprez-about", summary="VocPrez About", include_in_schema=len(ENABLED_PREZS) > 1
)
async def vocprez_about(request: Request):
    """Returns the VocPrez About page"""
    return await about(request)


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
    profile, mediatype = connegp_placeholder(request, vocprez_members.general_class)
    list_query = generate_listing_construct(
        vocprez_members.general_class, None, page, per_page, profile
    )
    count_query = generate_listing_count_construct(
        general_class=vocprez_members.general_class
    )
    return await return_data([list_query, count_query], mediatype, profile, "VocPrez")


@router.get("/scheme/{scheme_id}", summary="Get ConceptScheme")
@router.get("/vocab/{scheme_id}", summary="Get ConceptScheme")
@router.get("/collection/{collection_id}", summary="Get Collection")
async def scheme_endpoint(request: Request):
    """Returns a VocPrez skos:ConceptScheme in the necessary profile & mediatype"""
    vp_item = VocPrezItem(**request.path_params, url=str(request.url.path))
    profile, mediatype = connegp_placeholder(request, vp_item.general_class)
    query = generate_item_construct(vp_item.uri, profile)
    return await return_data(query, mediatype, profile, "VocPrez")


async def concept(
    request: Request,
):
    concept_renderer = VocPrezConceptRenderer(request)
    include_inferencing = True
    if concept_renderer.profile == "vocpub_supplied":
        include_inferencing = False
    sparql_result = await get_concept_construct(
        concept_id=concept_renderer.concept_id,
        scheme_id=concept_renderer.scheme_id,
        concept_uri=concept_renderer.concept_uri,
        include_inferencing=include_inferencing,
    )
    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    concept = VocPrezConcept(
        sparql_result, id=concept_renderer.concept_id, uri=concept_renderer.concept_uri
    )
    concept_renderer.set_concept(concept)
    profile = concept_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(concept_renderer.concept_uri),
            concept_renderer.profile_details.profiles_formats,
            concept_renderer.profile_details.available_profiles_dict,
        )
        return concept_renderer.render(alt_profiles_graph=alt_profiles_graph)
    return concept_renderer.render()


@router.get("/scheme/{scheme_id}/{concept_id}", summary="Get Concept")
@router.get("/vocab/{scheme_id}/{concept_id}", summary="Get Concept")
async def concept_endpoint(request: Request):
    """Returns a VocPrez skos:Concept in the necessary profile & mediatype"""
    return await concept(request)


@router.get(
    "/vocprez-profiles",
    summary="VocPrez Profiles",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def vocprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by VocPrez"""
    return await profiles_func(request, "VocPrez")
