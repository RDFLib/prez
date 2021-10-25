from urllib.parse import quote_plus

import fastapi
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from rdflib.namespace import SKOS
from rdflib import URIRef

from config import *
from routers import vocprez_router
from services.app_service import *

app = fastapi.FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(TEMPLATES_DIRECTORY)


def build_cache():
    # needs to depend on what *Prezs are enabled

    # 1. query DB for seeAlso map
    # get index dict of graph & admin graph URIs
    # system_index = {
    #     "vocab_uri": [
    #         "background_uri",
    #         "vocab_system_uri"
    #     ]
    # }
    #
    pass


def configure():
    build_cache()
    configure_routing()


def configure_routing():
    if "vocprez" in ENABLED_PREZS:
        app.include_router(vocprez_router.router)


@app.get("/", summary="Home page")
async def index(request: Request):
    """Displays the home page of Prez"""
    template_context = {"request": request, "enabled_prezs": ENABLED_PREZS}
    return templates.TemplateResponse("index.html", context=template_context)


@app.get("/sparql", summary="SPARQL page")
async def sparql(request: Request):
    """Displays the sparql page of Prez"""
    template_context = {"request": request}
    return templates.TemplateResponse("sparql.html", context=template_context)


@app.get("/search", summary="Search page")
async def search(request: Request):
    """Displays the search page of Prez"""
    template_context = {"request": request}
    return templates.TemplateResponse("search.html", context=template_context)


@app.get("/about", summary="About page")
async def about(request: Request):
    """Displays the about page of Prez"""
    template_context = {"request": request}
    return templates.TemplateResponse("about.html", context=template_context)


@app.get("/prezs", summary="Enabled Prezs")
async def prezs(request: Request):
    """Returns a list of the enabled *Prez 'modules'"""
    uri = str(request.base_url)
    return JSONResponse(
        content={"uri": uri, "prezs": [f"{uri}{prez}" for prez in ENABLED_PREZS]},
        media_type="application/json",
        headers=request.headers,
    )


@app.get("/object", summary="Get object")
async def object(request: Request, uri: str):
    """Generic endpoint to get any object. Redirects to the appropriate endpoint based on type"""
    # query to get basic info for object
    sparql_response = await get_object(uri)
    params = (
        str(request.query_params)
        .replace(f"&uri={quote_plus(uri)}", "")
        .replace(f"uri={quote_plus(uri)}", "")  # if uri param at start of query string
    )
    # removes the leftover "?" if no other params than uri
    if params != "":
        params = "?" + params[1:]  # will start with & instead of ?
    object_type = URIRef(sparql_response[0]["type"]["value"])
    object_id = sparql_response[0]["id"]["value"]
    object_cs_id = (
        sparql_response[0]["cs_id"]["value"]
        if sparql_response[0].get("cs_id") is not None
        else None
    )

    # redirect according to type (IF appropriate prez module is enabled)
    if object_type == SKOS.ConceptScheme:
        if "vocprez" not in ENABLED_PREZS:
            raise HTTPException(status_code=404, detail="This resource does not exist")
        return RedirectResponse(
            f"{vocprez_router.router.url_path_for('scheme', scheme_id=object_id)}{params}",
            headers=request.headers,
        )
        # return await vocprez_router.scheme_endpoint(request, scheme_uri=uri)

    return uri


if __name__ == "__main__":
    configure()
    uvicorn.run("app:app", port=PORT, host=SYSTEM_URI, reload=True)
else:
    configure()
