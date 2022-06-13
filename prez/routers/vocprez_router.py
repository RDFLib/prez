from fastapi import APIRouter, Request, HTTPException
import asyncio

from prez.renderers.vocprez import *
from prez.services.vocprez_service import *
from prez.models.vocprez import *
from prez.profiles.generate_profiles import (
    ProfileDetails,
    get_general_profiles,
    get_class_based_and_default_profiles,
    retrieve_relevant_shapes,
    build_alt_graph,
)
from prez.utils import templates
from prez.view_funcs import profiles_func
from prez.config import *

router = APIRouter(tags=["VocPrez"] if len(ENABLED_PREZS) > 1 else [])


async def home(request: Request):
    instances_classes = [str(DCAT.Dataset)]
    (
        profiles_g,
        preferred_classes_and_profiles,
        profiles,
        profiles_formats,
    ) = await get_general_profiles(DCAT.Dataset)

    # find the available profiles
    available_profiles, default_profile = await get_class_based_and_default_profiles(
        "http://localhost:8000",  # should cater for multiple *Prezs - i.e. when vocprez_home is /vocprez, not /
        preferred_classes_and_profiles,
        "VocPrez",
    )

    # find the most specific class for the feature
    for klass, _ in reversed(preferred_classes_and_profiles):
        if klass in instances_classes:
            most_specific_class = klass
            break

    dataset_renderer = VocPrezDatasetRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        available_profiles=profiles,
        default_profile=default_profile,
    )
    profile = dataset_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef("http://localhost:8000"), profiles_formats, available_profiles
        )
        return dataset_renderer.render(alt_profiles_graph=alt_profiles_graph)
    sparql_result = await get_dataset_construct()
    dataset = VocPrezDataset(sparql_result)
    dataset_renderer.set_dataset(dataset)
    return dataset_renderer.render()


@router.get(
    "/vocprez", summary="VocPrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def vocprez_home(request: Request):
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
async def schemes(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of VocPrez skos:ConceptSchemes in the necessary profile & mediatype"""
    scheme_count, sparql_result = await asyncio.gather(
        count_schemes(), list_schemes(page, per_page)
    )
    # sparql_result = await list_schemes()
    scheme_list = VocPrezSchemeList(sparql_result)
    scheme_list_renderer = VocPrezSchemeListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Concept Scheme list",
        "A list of skos:ConceptSchemes",
        scheme_list,
        page,
        per_page,
        int(scheme_count[0]["count"]["value"]),
    )
    return scheme_list_renderer.render()


@router.get("/scheme/{scheme_id}", summary="Get ConceptScheme")
@router.get("/vocab/{scheme_id}", summary="Get ConceptScheme")
async def scheme(request: Request, scheme_id: str):
    """Returns a VocPrez skos:ConceptScheme in the necessary profile & mediatype"""
    return await scheme_endpoint(request, scheme_id=scheme_id)


async def scheme_endpoint(
    request: Request, scheme_id: Optional[str] = None, scheme_uri: Optional[str] = None
):
    instance_classes = [str(SKOS.ConceptScheme)]
    (
        profiles_g,
        preferred_classes_and_profiles,
        profiles,
        profiles_formats,
    ) = await get_general_profiles(SKOS.ConceptScheme)

    # find the available profiles
    available_profiles, default_profile = await get_class_based_and_default_profiles(
        "http://localhost:8000", preferred_classes_and_profiles, "VocPrez"
    )

    # find the most specific class for the feature
    for klass, _ in reversed(preferred_classes_and_profiles):
        if klass in instance_classes:
            most_specific_class = klass
            break

    scheme_renderer = VocPrezSchemeRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
        available_profiles,
        default_profile,
    )
    include_inferencing = True
    if scheme_renderer.profile == "vocpub_supplied":
        include_inferencing = False

    results = await asyncio.gather(
        get_scheme_construct1(
            scheme_id=scheme_id,
            scheme_uri=scheme_uri,
            include_inferencing=include_inferencing,
        ),
        get_scheme_construct2(
            scheme_id=scheme_id,
            scheme_uri=scheme_uri,
            include_inferencing=include_inferencing,
        ),
    )

    sparql_result = Graph()
    for g in results:
        sparql_result += g

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    scheme = VocPrezScheme(sparql_result, id=scheme_id, uri=scheme_uri)
    scheme_renderer.set_scheme(scheme)
    profile = scheme_renderer.profile
    if profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(scheme.uri), profiles_formats, available_profiles
        )
        return scheme_renderer.render(alt_profiles_graph=alt_profiles_graph)
    return scheme_renderer.render()


@router.get("/collection", summary="List Collections")
async def collections(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of VocPrez skos:Collections in the necessary profile & mediatype"""
    collection_count, sparql_result = await asyncio.gather(
        count_collections(), list_collections(page, per_page)
    )
    # sparql_result = await list_collections()
    collection_list = VocPrezCollectionList(sparql_result)
    collection_list_renderer = VocPrezCollectionListRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        "Collection list",
        "A list of skos:Collection",
        collection_list,
        page,
        per_page,
        int(collection_count[0]["count"]["value"]),
    )
    return collection_list_renderer.render()


async def collection_endpoint(
    request: Request,
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
):
    collection_renderer = VocPrezCollectionRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
    )
    include_inferencing = True
    if collection_renderer.profile == "vocpub_supplied":
        include_inferencing = False
    results = await asyncio.gather(
        get_collection_construct1(
            collection_id=collection_id,
            collection_uri=collection_uri,
            include_inferencing=include_inferencing,
        ),
        get_collection_construct2(
            collection_id=collection_id,
            collection_uri=collection_uri,
            include_inferencing=include_inferencing,
        ),
    )

    sparql_result = Graph()
    for g in results:
        sparql_result += g

    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    collection = VocPrezCollection(sparql_result, id=collection_id, uri=collection_uri)
    collection_renderer.set_collection(collection)
    return collection_renderer.render()


@router.get("/collection/{collection_id}", summary="Get Collection")
async def collection(request: Request, collection_id: str):
    """Returns a VocPrez skos:Collection in the necessary profile & mediatype"""
    return await collection_endpoint(request, collection_id=collection_id)


async def concept_endpoint(
    request: Request,
    scheme_id: Optional[str] = None,
    concept_id: Optional[str] = None,
    concept_uri: Optional[str] = None,
):
    feature_classes = [str(SKOS.Concept)]
    (
        profiles_g,
        preferred_classes_and_profiles,
        profiles,
        profiles_formats,
    ) = await get_general_profiles(SKOS.Concept)

    # find the available profiles
    available_profiles, default_profile = await get_class_based_and_default_profiles(
        concept_uri, preferred_classes_and_profiles, "VocPrez"
    )

    # find the most specific class for the feature
    for klass, _ in reversed(preferred_classes_and_profiles):
        if klass in feature_classes:
            most_specific_class = klass
            break

    concept_renderer = VocPrezConceptRenderer(
        request,
        str(
            request.url.remove_query_params(
                keys=[key for key in request.query_params.keys() if key != "uri"]
            )
        ),
        available_profiles=profiles,
        default_profile=default_profile,
    )
    include_inferencing = True
    if concept_renderer.profile == "vocpub_supplied":
        include_inferencing = False
    sparql_result = await get_concept_construct(
        concept_id=concept_id,
        scheme_id=scheme_id,
        concept_uri=concept_uri,
        include_inferencing=include_inferencing,
    )
    if len(sparql_result) == 0:
        raise HTTPException(status_code=404, detail="Not Found")
    concept = VocPrezConcept(sparql_result, id=concept_id, uri=concept_uri)
    concept_renderer.set_concept(concept)
    # profile = concept_renderer.profile
    # if profile == "alt":
    #     alt_profiles_graph = await build_alt_graph(
    #         URIRef(feature_uri), profiles_formats, available_profiles
    #     )
    #     return feature_renderer.render(alt_profiles_graph=alt_profiles_graph)
    return concept_renderer.render()


@router.get("/scheme/{scheme_id}/{concept_id}", summary="Get Concept")
@router.get("/vocab/{scheme_id}/{concept_id}", summary="Get Concept")
async def concept(request: Request, scheme_id: str, concept_id: str):
    """Returns a VocPrez skos:Concept in the necessary profile & mediatype"""
    return await concept_endpoint(request, scheme_id=scheme_id, concept_id=concept_id)


@router.get(
    "/vocprez-profiles",
    summary="VocPrez Profiles",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def vocprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by VocPrez"""
    return await profiles_func(request, "vocprez")
