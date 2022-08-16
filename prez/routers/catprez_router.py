from async_lru import alru_cache
from fastapi import APIRouter, Request, HTTPException

from prez.models.catprez import *
from prez.profiles.generate_profiles import (
    build_alt_graph,
)
from prez.renderers.catprez import *
from prez.renderers.catprez.catprez_conformance_renderer import CatPrezConformanceRenderer
from prez.services.catprez_service import *
from prez.utils import templates
from prez.view_funcs import profiles_func

router = APIRouter(tags=["CatPrez"] if len(ENABLED_PREZS) > 1 else [])


async def home(request: Request):
    """Returns the CatPrez home page in the necessary profile & mediatype"""
    home_renderer = CatPrezResourceRenderer(request)
    if home_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            PREZ.CatPrezHome,
            home_renderer.profile_details.profiles_formats,
            home_renderer.profile_details.available_profiles_dict,
        )
        return home_renderer.render(alt_profiles_graph=alt_profiles_graph)
    sparql_result = await get_catprez_home_construct()
    resource = CatPrezResource(sparql_result, id="catprez")
    home_renderer.set_resource(resource)
    return home_renderer.render()


@alru_cache(maxsize=5)
@router.get(
    "/catprez", summary="CatPrez Home", include_in_schema=len(ENABLED_PREZS) > 1
)
async def catprez_home_endpoint(request: Request):
    """Returns a CatPrez dcat:Dataset in the necessary profile & mediatype"""
    return await home(request)


async def about(request: Request):
    return templates.TemplateResponse(
        "catprez/catprez_about.html", {"request": request}
    )


@router.get(
    "/catprez-about", summary="CatPrez About", include_in_schema=len(ENABLED_PREZS) > 1
)
async def catprez_about(request: Request):
    """Returns the CatPrez About page"""
    return await about(request)


@router.get("/catalogs", summary="List Catalogs")
async def catalogs_endpoint(
    request: Request,
    page: int = 1,
    per_page: int = 20,
):
    """Returns a list of CatPrez dcat:Catalog instances in the necessary profile & mediatype"""
    catalog_count, sparql_result = await asyncio.gather(
        count_catalogs(), list_catalogs(page, per_page)
    )
    catalog_list = CatPrezCatalogs(sparql_result)
    catalog_list_renderer = CatPrezCatalogsRenderer(
        request,
        catalog_list,
        page,
        per_page,
        int(catalog_count[0]["count"]["value"]),
    )
    if catalog_list_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(catalog_list_renderer.instance_uri),
            catalog_list_renderer.profile_details.profiles_formats,
            catalog_list_renderer.profile_details.available_profiles_dict,
        )
        return catalog_list_renderer.render(alt_profiles_graph=alt_profiles_graph)
    return catalog_list_renderer.render()


@router.get("/catalog/{catalog_id}", summary="Get Catalog")
async def catalog_endpoint(request: Request):
    """Returns a CatPrez dcat:Catalog in the necessary profile & mediatype"""
    return await catalog(request)


async def catalog(request: Request):
    """Returns a CatPrez dcat:Catalog in the necessary profile & mediatype"""
    catalog_renderer = CatPrezCatalogRenderer(request)

    if catalog_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(catalog_renderer.instance_uri),
            catalog_renderer.profile_details.profiles_formats,
            catalog_renderer.profile_details.available_profiles_dict,
        )
        return catalog_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        sparql_result = await get_catalog_construct(
            catalog_id=catalog_renderer.catalog_id,
            catalog_uri=catalog_renderer.catalog_uri,
        )
        if len(sparql_result) == 0:
            raise HTTPException(status_code=404, detail="Not Found")
        dataset = CatPrezCatalog(
            sparql_result,
            id=catalog_renderer.catalog_id,
            uri=catalog_renderer.instance_uri,
        )
        catalog_renderer.set_catalog(dataset)
        return catalog_renderer.render()


@router.get("/catalog/{catalog_id}/{resource_id}", summary="Get Resource")
async def resource_endpoint(request: Request):
    """Returns a CatPrez dcat:Resource in the necessary profile & mediatype"""
    return await resource(request)


async def resource(request: Request):
    """Returns a CatPrez dcat:Resource in the necessary profile & mediatype"""
    resource_renderer = CatPrezResourceRenderer(request)

    if resource_renderer.profile == "alt":
        alt_profiles_graph = await build_alt_graph(
            URIRef(resource_renderer.instance_uri),
            resource_renderer.profile_details.profiles_formats,
            resource_renderer.profile_details.available_profiles_dict,
        )
        return resource_renderer.render(alt_profiles_graph=alt_profiles_graph)
    else:
        sparql_result = await get_resource_construct(
            resource_id=resource_renderer.resource_id,
            resource_uri=resource_renderer.resource_uri,
        )

        if len(sparql_result) == 0:
            raise HTTPException(status_code=404, detail="Not Found")
        resource = CatPrezResource(
            sparql_result,
            id=resource_renderer.resource_id,
            uri=resource_renderer.instance_uri,
        )
        resource_renderer.set_resource(resource)
        return resource_renderer.render()


@router.get(
    "/catprez-profiles",
    summary="CatPrez Profiles",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def catprez_profiles(request: Request):
    """Returns a JSON list of the profiles accepted by CatPrez"""
    return await profiles_func(request, "CatPrez")


@router.get("/conformance", summary="Conformance")
async def conformance(request: Request):
    """Returns the SpacePrez conformance page in the necessary profile & mediatype"""
    conformance_renderer = CatPrezConformanceRenderer(request)
    return conformance_renderer.render()


@router.get(
    "/catprez-about",
    summary="CatPrez About",
    include_in_schema=len(ENABLED_PREZS) > 1,
)
async def catprez_about(request: Request):
    """Returns the SpacePrez about page in the necessary profile & mediatype"""
    return templates.TemplateResponse(
        "catprez/catprez_about.html", {"request": request}
    )
