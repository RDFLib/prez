from fastapi import APIRouter, Request

from renderers.vocprez import *
from services.vocprez_service import *
from models.vocprez import *

router = APIRouter(prefix="/vocprez", tags=["VocPrez"])


@router.get("/", summary="VocPrez Dataset")
async def dataset(request: Request):
    """Returns a VocPrez dcat:Dataset in the necessary profile & mediatype"""
    sparql_result = await get_dataset()
    # assume 1 dataset for now
    dataset = VocPrezDataset(sparql_result)
    dataset_renderer = VocPrezDatasetRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        dataset,
    )
    return dataset_renderer.render()


@router.get("/scheme", summary="List ConceptSchemes")
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
async def scheme(request: Request, scheme_id: str):
    """Returns a VocPrez skos:ConceptScheme in the necessary profile & mediatype"""
    sparql_result = await get_scheme(scheme_id)
    concept_result = await get_concept_hierarchy(scheme_id)
    scheme = VocPrezScheme(sparql_result, concept_result)
    scheme_renderer = VocPrezSchemeRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        scheme,
    )
    return scheme_renderer.render()


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
    sparql_result = await get_collection(collection_id)
    concept_result = await get_collection_concepts(collection_id)
    collection = VocPrezCollection(sparql_result, concept_result)
    collection_renderer = VocPrezCollectionRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        collection,
    )
    return collection_renderer.render()


@router.get("/scheme/{scheme_id}/{concept_id}", summary="Get Concept")
async def concept(request: Request, scheme_id: str, concept_id: str):
    """Returns a VocPrez skos:Concept in the necessary profile & mediatype"""
    sparql_result = await get_concept(scheme_id, concept_id)
    broader_result = await get_broader_concepts(concept_id)
    narrower_result = await get_narrower_concepts(concept_id)
    concept = VocPrezConcept(sparql_result, broader_result, narrower_result)
    concept_renderer = VocPrezConceptRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        concept,
    )
    return concept_renderer.render()
