import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from rdflib import Graph
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from prez.dependencies import (
    LuceneCQLRequest,
    get_data_repo,
    lucene_cql_get_request_dependency,
    lucene_cql_post_request_dependency,
)
from prez.repositories import Repo
from prez.reference_data.prez_ns import OGCE
from prez.routers.api_extras_examples import responses
from prez.services.query_generation.cql_lucene_json import (
    generate_cql_lucene_json_sparql,
)

router = APIRouter(tags=["ogcprez"])

SPARQL_RESULTS_JSON = "application/sparql-results+json"


async def _execute_lucene_cql_query(repo: Repo, request_params: LuceneCQLRequest):
    query = generate_cql_lucene_json_sparql(
        q=request_params.q,
        filter_json=request_params.filter_json,
        facets=request_params.facets,
        limit=request_params.limit,
        offset=request_params.offset,
    )
    query_result = await repo.sparql(
        query,
        [(b"accept", SPARQL_RESULTS_JSON.encode("utf-8"))],
        method="POST",
    )

    if isinstance(query_result, dict):
        return Response(
            content=json.dumps(query_result),
            media_type=SPARQL_RESULTS_JSON,
        )
    if isinstance(query_result, Graph):
        raise HTTPException(
            status_code=500,
            detail="Lucene-backed /cql requires a SPARQL JSON response.",
        )
    if not isinstance(query_result, httpx.Response):
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected SPARQL response type: {type(query_result)!r}",
        )

    headers = {
        k: v
        for k, v in query_result.headers.items()
        if k.lower() not in ("transfer-encoding", "content-length")
    }
    headers["Content-Type"] = SPARQL_RESULTS_JSON
    return StreamingResponse(
        query_result.aiter_raw(),
        status_code=query_result.status_code,
        headers=headers,
        media_type=SPARQL_RESULTS_JSON,
        background=BackgroundTask(query_result.aclose),
    )


@router.get(
    "/cql",
    summary="Lucene-backed CQL GET endpoint",
    name=OGCE["cql-get"],
    responses=responses,
)
async def lucene_cql_get(
    request_params: LuceneCQLRequest = Depends(lucene_cql_get_request_dependency),
    data_repo: Repo = Depends(get_data_repo),
):
    return await _execute_lucene_cql_query(data_repo, request_params)


@router.post(
    "/cql",
    summary="Lucene-backed CQL POST endpoint",
    name=OGCE["cql-post"],
    responses=responses,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "filter": {"type": "object"},
                            "facets": {
                                "type": "array",
                                "items": {"type": "string", "format": "uri"},
                            },
                            "limit": {"type": "integer", "minimum": 1},
                            "offset": {"type": "integer", "minimum": 0},
                        },
                    }
                }
            }
        }
    },
)
async def lucene_cql_post(
    request_params: LuceneCQLRequest = Depends(lucene_cql_post_request_dependency),
    data_repo: Repo = Depends(get_data_repo),
):
    return await _execute_lucene_cql_query(data_repo, request_params)
