import io
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse, Response
from rdflib import Graph, Namespace
from starlette.background import BackgroundTask
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import StreamingResponse

from prez.dependencies import get_repo
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.renderers.renderer import return_annotated_rdf
from prez.sparql.methods import Repo

PREZ = Namespace("https://prez.dev/")

router = APIRouter(tags=["SPARQL"])


@router.post("/sparql")
async def sparql_post_passthrough(
    # To maintain compatibility with the other SPARQL endpoints,
    # /sparql POST endpoint is not a JSON API, it uses
    # values encoded with x-www-form-urlencoded
    query: Annotated[
        str, Form()
    ],  # Pydantic validation prevents update queries (the Form would need to be "update")
    request: Request,
    repo: Repo = Depends(get_repo),
):
    return await sparql_endpoint_handler(query, request, repo, method="POST")


@router.get("/sparql")
async def sparql_get_passthrough(
    query: str,
    request: Request,
    repo: Repo = Depends(get_repo),
):
    return await sparql_endpoint_handler(query, request, repo, method="GET")


async def sparql_endpoint_handler(
    query: str, request: Request, repo: Repo, method="GET"
):
    request_mediatype = request.headers.get("accept").split(",")[0]
    # can't default the MT where not provided as it could be
    # graph (CONSTRUCT like queries) or tabular (SELECT queries)

    # Intercept "+anot" mediatypes
    if "anot+" in request_mediatype:
        prof_and_mt_info = ProfilesMediatypesInfo(
            request=request, classes=frozenset([PREZ.SPARQLQuery])
        )
        non_anot_mediatype = request_mediatype.replace("anot+", "")
        request._headers = Headers({**request.headers, "accept": non_anot_mediatype})
        response = await repo.sparql(query, request.headers.raw, method=method)
        await response.aread()
        g = Graph()
        g.parse(data=response.text, format=non_anot_mediatype)
        graph = await return_annotated_rdf(g, prof_and_mt_info.profile, repo)
        content = io.BytesIO(
            graph.serialize(format=non_anot_mediatype, encoding="utf-8")
        )
        return StreamingResponse(
            content=content,
            media_type=non_anot_mediatype,
            headers=prof_and_mt_info.profile_headers,
        )
    query_result: httpx.Response = await repo.sparql(
        query, request.headers.raw, method=method
    )
    if isinstance(query_result, dict):
        return JSONResponse(content=query_result)
    elif isinstance(query_result, Graph):
        return Response(
            content=query_result.serialize(format="text/turtle"), status_code=200
        )

    dispositions = query_result.headers.get_list("Content-Disposition")
    for disposition in dispositions:
        if disposition.lower().startswith("attachment"):
            is_attachment = True
            break
    else:
        is_attachment = False
    if is_attachment:
        # remove transfer-encoding chunked, disposition=attachment, and content-length
        headers = dict()
        for k, v in query_result.headers.items():
            if k.lower() not in (
                "transfer-encoding",
                "content-disposition",
                "content-length",
            ):
                headers[k] = v
        content = await query_result.aread()
        await query_result.aclose()
        return Response(
            content=content,
            status_code=query_result.status_code,
            headers=headers,
        )
    else:
        return StreamingResponse(
            query_result.aiter_raw(),
            status_code=query_result.status_code,
            headers=dict(query_result.headers),
            background=BackgroundTask(query_result.aclose),
        )
