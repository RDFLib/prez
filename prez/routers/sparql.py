import io

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from rdflib import Namespace, Graph
from starlette.background import BackgroundTask
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import StreamingResponse

from prez.dependencies import get_data_repo, get_system_repo
from prez.renderers.renderer import return_annotated_rdf
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs

PREZ = Namespace("https://prez.dev/")

router = APIRouter(tags=["SPARQL"])


# TODO: Split this into two routes on the same /sparql path.
#  One to handle SPARQL GET requests, the other for SPARQL POST requests.


@router.get("/sparql")
async def sparql_endpoint(
    query: str,
    request: Request,
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
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
        response = await repo.sparql(query, request.headers.raw)
        await response.aread()
        g = Graph()
        g.parse(data=response.text, format=non_anot_mediatype)
        graph = await return_annotated_rdf(g, repo, system_repo)
        content = io.BytesIO(
            graph.serialize(format=non_anot_mediatype, encoding="utf-8")
        )
        return StreamingResponse(
            content=content,
            media_type=non_anot_mediatype,
            headers=pmts.generate_response_headers(),
        )
    else:
        query_result = await repo.sparql(query, request.headers.raw)
        if isinstance(query_result, dict):
            return JSONResponse(content=query_result)
        elif isinstance(query_result, Graph):
            return Response(
                content=query_result.serialize(format="text/turtle"), status_code=200
            )
        else:
            return StreamingResponse(
                query_result.aiter_raw(),
                status_code=query_result.status_code,
                headers=dict(query_result.headers),
                background=BackgroundTask(query_result.aclose),
            )
