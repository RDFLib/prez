import asyncio

from fastapi import APIRouter, Request, Body
from pydantic import BaseModel
from rdflib import Namespace, Graph
from starlette.responses import PlainTextResponse, JSONResponse

from prez.renderers.renderer import return_rdf
from prez.sparql.methods import sparql_query

PREZ = Namespace("https://prez.dev/")

router = APIRouter(tags=["SPARQL"])

# TODO see: https://github.com/tiangolo/fastapi/issues/1788 for how to restructure this.


@router.get("/sparql", summary="Federated Sparql")
@router.get("/v/sparql", summary="VocPrez Sparql")
@router.get("/c/sparql", summary="CatPrez Sparql")
@router.get("/s/sparql", summary="SpacePrez Sparql")
async def sparql(
    request: Request,
):
    from prez.config import settings

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
    if start_of_path == "/sp":
        if len(settings.enabled_prezs) == 1:
            prez = settings.enabled_prezs[0]
        else:
            endpoints = {p: settings.sparql_creds[p]["endpoint"] for p in settings.enabled_prezs}
            unique_endpoints = {}
            for p, endpoint in endpoints.items():
                if endpoint not in unique_endpoints.values():
                    unique_endpoints[p] = endpoint
            results = await asyncio.gather(
                *[sparql_query(query, p) for p in unique_endpoints.keys()]
            )
            for result in results:
                if isinstance(result, PlainTextResponse):
                    return result
            if results[0][1].startswith("application/json"):
                combined_bindings = []
                for result in results:
                    for binding in result[2]["results"]["bindings"]:
                        binding["endpoint"] = {"type": "uri", "value": result[0]}
                        combined_bindings.append(binding)
                results[0][2]["results"]["bindings"] = combined_bindings
                return JSONResponse(results[0][2])
            # warning: the following is not a sensible way to return results.
            # the user cannot know which endpoint each result came from.
            # no current ideas for a better solution.
            elif results[0][1] == ("text/turtle"):
                graph = Graph(bind_namespaces="rdflib")
                graph.bind("prez", "https://prez.dev/")
                for res in results:
                    g = res[2]
                    graph.__iadd__(g)
                return await return_rdf(
                    graph, mediatype="text/anot+turtle", profile_headers={}
                )
    else:
        prez = pathmap.get(start_of_path)
    _, mt, result = await sparql_query(query, prez)
    if mt.startswith("application/json"):
        return JSONResponse(result)
    if len(result) > 0:
        return await return_rdf(result, mediatype=mt, profile_headers={})
    else:
        return PlainTextResponse(f"No results returned from {prez} SPARQL endpoint.")


# class Query(BaseModel):
#     q: str


@router.post("/sparql", summary="Federated Sparql")
@router.post("/v/sparql", summary="VocPrez Sparql")
@router.post("/c/sparql", summary="CatPrez Sparql")
@router.post("/s/sparql", summary="SpacePrez Sparql")
async def sparql(
    request: Request, query: str = Body(..., media_type="application/sparql-query")
):
    from prez.config import settings

    if not query:
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
    if start_of_path == "/sp":
        if len(settings.enabled_prezs) == 1:
            prez = settings.enabled_prezs[0]
        else:
            endpoints = {p: settings.sparql_creds[p]["endpoint"] for p in settings.enabled_prezs}
            unique_endpoints = {}
            for p, endpoint in endpoints.items():
                if endpoint not in unique_endpoints.values():
                    unique_endpoints[p] = endpoint
            results = await asyncio.gather(
                *[sparql_query(query, p) for p in unique_endpoints.keys()]
            )
            for result in results:
                if isinstance(result, PlainTextResponse):
                    return result
            if results[0][1].startswith("application/json"):
                combined_bindings = []
                for result in results:
                    for binding in result[2]["results"]["bindings"]:
                        binding["endpoint"] = {"type": "uri", "value": result[0]}
                        combined_bindings.append(binding)
                results[0][2]["results"]["bindings"] = combined_bindings
                return JSONResponse(results[0][2])
            # warning: the following is not a sensible way to return results.
            # the user cannot know which endpoint each result came from.
            # no current ideas for a better solution.
            elif results[0][1] == ("text/turtle"):
                graph = Graph(bind_namespaces="rdflib")
                graph.bind("prez", "https://prez.dev/")
                for res in results:
                    g = res[2]
                    graph.__iadd__(g)
                return await return_rdf(
                    graph, mediatype="text/anot+turtle", profile_headers={}
                )
    else:
        prez = pathmap.get(start_of_path)
    _, mt, result = await sparql_query(query, prez)
    if mt.startswith("application/json"):
        return JSONResponse(result)
    if len(result) > 0:
        return await return_rdf(result, mediatype=mt, profile_headers={})
    else:
        return PlainTextResponse(f"No results returned from {prez} SPARQL endpoint.")
