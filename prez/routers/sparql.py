from fastapi import APIRouter, Request
from rdflib import Namespace
from starlette.responses import PlainTextResponse, JSONResponse

from prez.renderers.renderer import return_rdf
from services.sparql_utils import sparql_construct, sparql_query

PREZ = Namespace("https://prez.dev/")

router = APIRouter(tags=["SPARQL"])


@router.get("/v/sparql", summary="VocPrez Sparql")
@router.get("/c/sparql", summary="CatPrez Sparql")
@router.get("/s/sparql", summary="SpacePrez Sparql")
async def sparql(
    request: Request,
):
    query = request.query_params.get("query")
    if not query:
        return PlainTextResponse(
            "A query must be provided as a query string argument (?query=<SPARQL query>)"
        )
    start_of_path = request.url.path[:3]
    pathmap = {
        "/v/": "VocPrez",
        "/c/": "CatPrez",
        "/s/": "SpacePrez",
    }
    prez = pathmap.get(start_of_path)
    mt, result = await sparql_query(query, prez)
    if mt.startswith("application/json"):
        return JSONResponse(result)
    if len(result) > 0:
        return await return_rdf(result, mediatype=mt, profile_headers=None)
    else:
        return PlainTextResponse(f"No results returned from {prez} SPARQL endpoint.")
