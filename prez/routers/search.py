from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import RDF, Literal
from rdflib.namespace import Namespace

from prez.config import settings
from prez.dependencies import get_data_repo, get_system_repo, generate_search_query
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.link_generation import add_prez_links
from temp.grammar import ConstructQuery

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
    search_query: ConstructQuery = Depends(generate_search_query),
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    search_query_str = search_query.to_string()
    target_classes = [PREZ.SearchResult]
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=request.query_params,
        classes=target_classes,
        listing=True,
        system_repo=system_repo,
    )
    await pmts.setup()

    item_graph, _ = await repo.send_queries([search_query_str], [])
    if "anot+" in pmts.selected["mediatype"]:
        await add_prez_links(
            item_graph, repo, settings.endpoint_structure
        )

    # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
    count = len(list(item_graph.subjects(RDF.type, PREZ.SearchResult)))
    item_graph.add((PREZ.SearchResult, PREZ["count"], Literal(count)))
    return await return_from_graph(
        item_graph,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        pmts.selected["class"],
        repo,
        system_repo,
    )
