import io
from typing import Annotated

from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse, Response
from rdflib import Namespace, Graph
from starlette.background import BackgroundTask
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import StreamingResponse

from prez.dependencies import get_data_repo, get_system_repo
from prez.renderers.renderer import return_annotated_rdf
from prez.repositories import Repo
from prez.routers.api_extras_examples import responses
from prez.services.connegp_service import NegotiatedPMTs

PREZ = Namespace("https://prez.dev/")

router = APIRouter(tags=["SPARQL"])


@router.post("/sparql")
async def sparql_post_passthrough(
    # To maintain compatibility with the other SPARQL endpoints,
    # /sparql POST endpoint is not a JSON API, it uses
    # values encoded with x-www-form-urlencoded
    query: Annotated[str, Form()],
    # Pydantic validation prevents update queries (the Form would need to be "update")
    request: Request,
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    return await sparql_endpoint_handler(
        query, request, repo, system_repo, method="POST"
    )


@router.get("/sparql", responses=responses)
async def sparql_get_passthrough(
    query: str,
    request: Request,
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    return await sparql_endpoint_handler(
        query, request, repo, system_repo, method="GET"
    )


async def sparql_endpoint_handler(
    query: str, request: Request, repo: Repo, system_repo, method="GET"
):
    pmts = NegotiatedPMTs(
        **{
            "headers": request.headers,
            "params": request.query_params,
            "classes": [PREZ.SPARQLQuery],
            "system_repo": system_repo,
        }
    )
    await pmts.setup()
    if (
        pmts.requested_mediatypes is not None
        and "anot+" in pmts.requested_mediatypes[0][0]
    ):
        non_anot_mediatype = pmts.requested_mediatypes[0][0].replace("anot+", "")
        request._headers = Headers({**request.headers, "accept": non_anot_mediatype})
        response = await repo.sparql(query, request.headers.raw, method=method)
        await response.aread()
        g = Graph()
        g.parse(data=response.text, format=non_anot_mediatype)
        annotations_graph = await return_annotated_rdf(g, repo, system_repo)
        g.__iadd__(annotations_graph)
        content = io.BytesIO(
            g.serialize(format=non_anot_mediatype, encoding="utf-8")
        )
        return StreamingResponse(
            content=content,
            media_type=non_anot_mediatype,
            headers=pmts.generate_response_headers(),
        )
    query_result: "httpx.Response" = await repo.sparql(
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
