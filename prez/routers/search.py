from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import URIRef
from rdflib.namespace import Namespace

from prez.dependencies import get_repo
from prez.reference_data.prez_ns import PREZ
from prez.repositories import Repo
from prez.services.listings import listing_function

router = APIRouter(tags=["Search"])
OGCE = Namespace(PREZ["endpoint/extended-ogc-records/"])


@router.get(
    path="/search",
    summary="Search",
    name=OGCE["search"],
)
async def search(
    request: Request,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    search_term: Optional[str] = None,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_repo),
):
    term = request.query_params.get("q")
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request,
        repo,
        system_repo,
        endpoint_uri,
        hierarchy_level=1,
        page=page,
        per_page=per_page,
        search_term=term,
    )

    # term = request.query_params.get("q")
    # limit = request.query_params.get("limit", 10)
    # offset = request.query_params.get("offset", 0)
    # pred_vals = request.query_params.get("predicates", settings.label_predicates)
    # query = SearchQuery(
    #     search_term=term,
    #     limit=limit,
    #     offset=offset,
    #     pred_vals=pred_vals,
    # ).render()
    # graph, _ = await repo.send_queries([query], [])
    #
    # count = len(list(graph.subjects(RDF.type, PREZ.SearchResult)))
    # graph.add((PREZ.SearchResult, PREZ["count"], Literal(count)))
    #
    # prof_and_mt_info = ProfilesMediatypesInfo(
    #     request=request, classes=frozenset([PREZ.SearchResult]), system_repo=system_repo
    # )
    # await populate_profile_and_mediatype(prof_and_mt_info, system_repo)
    #
    # req_mt = prof_and_mt_info.req_mediatypes
    # if req_mt:
    #     if list(req_mt)[0] == "application/sparql-query":
    #         return PlainTextResponse(query, media_type="application/sparql-query")
    #
    # if "anot+" in prof_and_mt_info.mediatype:
    #     await add_prez_links(graph, repo)
    #
    # return await return_from_graph(
    #     graph,
    #     mediatype=prof_and_mt_info.mediatype,
    #     profile=URIRef("https://prez.dev/profile/open-object"),
    #     profile_headers=prof_and_mt_info.profile_headers,
    #     selected_class=prof_and_mt_info.selected_class,
    #     repo=repo,
    # )
