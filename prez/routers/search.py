from fastapi import APIRouter, Request, Depends
from fastapi.responses import PlainTextResponse
from rdflib import URIRef, Literal
from rdflib.namespace import RDF

from prez.config import settings
from prez.dependencies import get_repo
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo, populate_profile_and_mediatype
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph
from prez.services.link_generation import _add_prez_links
from prez.sparql.methods import Repo
from prez.sparql.search_query import SearchQuery

router = APIRouter(tags=["Search"])


@router.get("/search", summary="Search")
async def search(
    request: Request,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_repo),
):
    term = request.query_params.get("q")
    limit = request.query_params.get("limit", 10)
    offset = request.query_params.get("offset", 0)
    pred_vals = request.query_params.get("predicates", settings.label_predicates)
    query = SearchQuery(
        search_term=term,
        limit=limit,
        offset=offset,
        pred_vals=pred_vals,
    ).render()
    graph, _ = await repo.send_queries([query], [])

    count = len(list(graph.subjects(RDF.type, PREZ.SearchResult)))
    graph.add((PREZ.SearchResult, PREZ["count"], Literal(count)))

    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=frozenset([PREZ.SearchResult]), system_repo=system_repo
    )
    await populate_profile_and_mediatype(prof_and_mt_info, system_repo)

    req_mt = prof_and_mt_info.req_mediatypes
    if req_mt:
        if list(req_mt)[0] == "application/sparql-query":
            return PlainTextResponse(query, media_type="application/sparql-query")

    if "anot+" in prof_and_mt_info.mediatype:
        await _add_prez_links(graph, repo, system_repo)

    return await return_from_graph(
        graph,
        mediatype=prof_and_mt_info.mediatype,
        profile=URIRef("https://prez.dev/profile/open-object"),
        profile_headers=prof_and_mt_info.profile_headers,
        selected_class=prof_and_mt_info.selected_class,
        repo=repo,
    )
