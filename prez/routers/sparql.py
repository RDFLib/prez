import io

from fastapi import APIRouter, Depends
from rdflib import Namespace, Graph
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

# TODO: Split this into two routes on the same /sparql path.
#  One to handle SPARQL GET requests, the other for SPARQL POST requests.


@router.get("/sparql")
async def sparql_endpoint(
    query: str,
    request: Request,
    repo: Repo = Depends(get_repo),
):
    request_mediatype = request.headers.get("accept").split(",")[
        0
    ]  # can't default the MT where not provided as it could be
    # graph (CONSTRUCT like queries) or tabular (SELECT queries)

    # Intercept "+anot" mediatypes
    if "anot+" in request_mediatype:
        prof_and_mt_info = ProfilesMediatypesInfo(
            request=request, classes=frozenset([PREZ.SPARQLQuery])
        )
        non_anot_mediatype = request_mediatype.replace("anot+", "")
        request._headers = Headers({**request.headers, "accept": non_anot_mediatype})
        response = await repo.sparql(request)
        await response.aread()
        g = Graph()
        g.parse(data=response.text, format=non_anot_mediatype)
        graph = await return_annotated_rdf(g, prof_and_mt_info.profile)
        content = io.BytesIO(
            graph.serialize(format=non_anot_mediatype, encoding="utf-8")
        )
        return StreamingResponse(
            content=content,
            media_type=non_anot_mediatype,
            headers=prof_and_mt_info.profile_headers,
        )
    else:
        response = await repo.sparql(query, request.headers.raw)
        return StreamingResponse(
            response.aiter_raw(),
            status_code=response.status_code,
            headers=dict(response.headers),
            background=BackgroundTask(response.aclose),
        )
