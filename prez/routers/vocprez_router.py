from async_lru import alru_cache
from fastapi import APIRouter, Request, HTTPException

from prez.models.vocprez import *
from prez.profiles.generate_profiles import (
    build_alt_graph,
)
from prez.renderers.vocprez import *
from prez.services.vocprez_service import *
from prez.utils import templates
from prez.view_funcs import profiles_func

router = APIRouter(tags=["VocPrez"] if len(ENABLED_PREZS) > 1 else [])


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


@alru_cache(maxsize=5)
@router.get(
    "/vocprez", summary="VocPrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def vocprez_home_endpoint(request: Request):
    """Returns a VocPrez dcat:Dataset in the necessary profile & mediatype"""
    return await home(request)


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


@router.get("/scheme", summary="List ConceptSchemes")
@router.get("/vocab", summary="List ConceptSchemes")
async def schemes_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of VocPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    scheme_count, sparql_result = await asyncio.gather(
        count_schemes(), list_schemes(page, per_page)
    )
    scheme_list = VocPrezSchemeList(sparql_result)
    scheme_list_renderer = VocPrezSchemeListRenderer(
        request,
        scheme_list,
        page,
        per_page,
        int(scheme_count[0]["count"]["value"]),
    )
    if scheme_list_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(scheme_list_renderer.instance_uri),
            scheme_list_renderer.profile_details.profiles_formats,
            scheme_list_renderer.profile_details.available_profiles_dict,
        )
        return scheme_list_renderer.render(alt_profiles_graph=alt_profiles_graph)
    return scheme_list_renderer.render()


@router.get("/scheme/{scheme_id}", summary="Get ConceptScheme")
@router.get("/vocab/{scheme_id}", summary="Get ConceptScheme")
async def scheme_endpoint(request: Request):
    """Returns a VocPrez skos:ConceptScheme in the necessary profile & mediatype"""
    return await scheme(request)


async def scheme(request: Request):
    scheme_renderer = VocPrezSchemeRenderer(request)
    include_inferencing = True
    if scheme_renderer.profile == "vocpub_supplied":
        include_inferencing = False

    results = await asyncio.gather(
        get_scheme_construct1(
            scheme_id=scheme_renderer.scheme_id,
            scheme_uri=scheme_renderer.scheme_uri,
            include_inferencing=include_inferencing,
        ),
        get_scheme_construct2(
            scheme_id=scheme_renderer.scheme_id,
            scheme_uri=scheme_renderer.scheme_uri,
            include_inferencing=include_inferencing,
        ),
    )

    sparql_result = Graph()
    for g in results:
        sparql_result += g

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    scheme = VocPrezScheme(
        sparql_result, id=scheme_renderer.scheme_id, uri=scheme_renderer.scheme_uri
    )
    scheme_renderer.set_scheme(scheme)
    if scheme_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(scheme_renderer.instance_uri),
            scheme_renderer.profile_details.profiles_formats,
            scheme_renderer.profile_details.available_profiles_dict,
        )
        return scheme_renderer.render(alt_profiles_graph=alt_profiles_graph)
    return scheme_renderer.render()


@router.get("/collection", summary="List Collections")
async def collections_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of VocPrez skos:Collections in the necessary profile & mediatype"""
    collection_count, sparql_result = await asyncio.gather(
        count_collections(), list_collections(page, per_page)
    )
    collection_list = VocPrezCollectionList(sparql_result)
    collection_list_renderer = VocPrezCollectionListRenderer(
        request,
        PREZ.VocPrezCollectionList,
        collection_list,
        page,
        per_page,
        int(collection_count[0]["count"]["value"]),
    )
    return collection_list_renderer.render()


@router.get("/collection/{collection_id}", summary="Get Collection")
async def collection_endpoint(request: Request):
    """Returns a VocPrez skos:Collection in the necessary profile & mediatype"""
    return await collection(request)


async def collection(request: Request):
    collection_renderer = VocPrezCollectionRenderer(request)
    include_inferencing = True
    if collection_renderer.profile == "vocpub_supplied":
        include_inferencing = False
    results = await asyncio.gather(
        get_collection_construct1(
            collection_id=collection_renderer.collection_id,
            collection_uri=collection_renderer.collection_uri,
            include_inferencing=include_inferencing,
        ),
        get_collection_construct2(
            collection_id=collection_renderer.collection_id,
            collection_uri=collection_renderer.collection_uri,
            include_inferencing=include_inferencing,
        ),
    )

    sparql_result = Graph()
    for g in results:
        sparql_result += g

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    collection = VocPrezCollection(
        sparql_result,
        id=collection_renderer.collection_id,
        uri=collection_renderer.collection_uri,
    )
    collection_renderer.set_collection(collection)
    return collection_renderer.render()


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
