from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from connegp import Profile
from starlette.responses import JSONResponse

from renderers.vocprez import *
from services.vocprez_service import *
from models.vocprez import *

router = APIRouter(prefix="/vocprez", tags=["VocPrez"])

templates = Jinja2Templates(TEMPLATES_DIRECTORY)


@router.get("/", summary="VocPrez Home")
async def dataset(request: Request):
    """Returns a VocPrez dcat:Dataset in the necessary profile & mediatype"""
    dataset_renderer = VocPrezDatasetRenderer(
        request, str(request.url.remove_query_params(keys=request.query_params.keys()))
    )
    sparql_result = await get_dataset_construct()
    dataset = VocPrezDataset(sparql_result)
    dataset_renderer.set_dataset(dataset)
    return dataset_renderer.render()
    # template_context = {
    #     "request": request
    # }
    # return templates.TemplateResponse("vocprez/vocprez_home.html", context=template_context)


@router.get("/scheme", summary="List ConceptSchemes")
@router.get("/vocab", summary="List ConceptSchemes")
async def schemes(request: Request):
    """Returns a list of VocPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    sparql_result = await list_schemes()
    scheme_list = VocPrezSchemeList(sparql_result)
    scheme_list_renderer = VocPrezSchemeListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Concept Scheme list",
        "A list of skos:ConceptSchemes",
        scheme_list,
    )
    return scheme_list_renderer.render()


@router.get("/scheme/{scheme_id}", summary="Get ConceptScheme")
@router.get("/vocab/{scheme_id}", summary="Get ConceptScheme")
async def scheme(request: Request, scheme_id: str):
    """Returns a VocPrez skos:ConceptScheme in the necessary profile & mediatype"""
    # return await scheme_endpoint(request, scheme_id=scheme_id)
    scheme_renderer = VocPrezSchemeRenderer(
        request, str(request.url.remove_query_params(keys=request.query_params.keys()))
    )
    include_inferencing = True
    if scheme_renderer.profile == "vocpub_supplied":
        include_inferencing = False
    sparql_result = await get_scheme_construct(
        scheme_id=scheme_id, include_inferencing=include_inferencing
    )
    scheme = VocPrezScheme(sparql_result, id=scheme_id)
    scheme_renderer.set_scheme(scheme)
    return scheme_renderer.render()


# async def scheme_endpoint(request: Request, scheme_id: Optional[str] = None, scheme_uri: Optional[str] = None):
#     scheme_renderer = VocPrezSchemeRenderer(
#         request,
#         # str(request.url.remove_query_params(keys=request.query_params.keys()))
#         str(request.url)
#     )
#     sparql_result = await get_scheme_construct(scheme_id=scheme_id, scheme_uri=scheme_uri)
#     scheme = VocPrezScheme(sparql_result, id=scheme_id, uri=scheme_uri)
#     scheme_renderer.set_scheme(scheme)
#     return scheme_renderer.render()


@router.get("/collection", summary="List Collections")
async def collections(request: Request):
    """Returns a list of VocPrez skos:Collections in the necessary profile & mediatype"""
    sparql_result = await list_collections()
    collection_list = VocPrezCollectionList(sparql_result)
    collection_list_renderer = VocPrezCollectionListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Collection list",
        "A list of skos:Collection",
        collection_list,
    )
    return collection_list_renderer.render()


@router.get("/collection/{collection_id}", summary="Get Collection")
async def collection(request: Request, collection_id: str):
    """Returns a VocPrez skos:Collection in the necessary profile & mediatype"""
    collection_renderer = VocPrezCollectionRenderer(
        request, str(request.url.remove_query_params(keys=request.query_params.keys()))
    )
    sparql_result = await get_collection_construct(collection_id=collection_id)
    collection = VocPrezCollection(sparql_result, id=collection_id)
    collection_renderer.set_collection(collection)
    return collection_renderer.render()


@router.get("/scheme/{scheme_id}/{concept_id}", summary="Get Concept")
@router.get("/vocab/{scheme_id}/{concept_id}", summary="Get Concept")
async def concept(request: Request, scheme_id: str, concept_id: str):
    """Returns a VocPrez skos:Concept in the necessary profile & mediatype"""
    concept_renderer = VocPrezConceptRenderer(
        request, str(request.url.remove_query_params(keys=request.query_params.keys()))
    )
    include_inferencing = True
    if concept_renderer.profile == "vocpub_supplied":
        include_inferencing = False
    sparql_result = await get_concept_construct(
        concept_id=concept_id,
        scheme_id=scheme_id,
        include_inferencing=include_inferencing,
    )
    concept = VocPrezConcept(sparql_result, id=concept_id)
    concept_renderer.set_concept(concept)
    return concept_renderer.render()


@router.get("/profiles", summary="VocPrez Profiles")
async def profiles(request: Request):
    """Returns a JSON list of the profiles accepted by VocPrez"""
    import profiles

    profiles_renderer = VocPrezProfilesRenderer(
        request, str(request.url.remove_query_params(keys=request.query_params.keys()))
    )

    # get list of profiles from profiles.py
    profile_list = []
    for item in dir(profiles):
        if not item.startswith("__") and not item == "profiles":
            profile = getattr(profiles, item)
            if isinstance(profile, Profile):
                profile_list.append(dict(profile))
    profile_list.sort(key=lambda p: p["id"])
    profiles_renderer.set_profiles(profile_list)
    return profiles_renderer.render()
