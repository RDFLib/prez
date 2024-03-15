from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import URIRef
from rdflib.namespace import Namespace

from prez.dependencies import get_repo, get_system_repo
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
    system_repo: Repo = Depends(get_system_repo),
):
    term = request.query_params.get("q")
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request=request,
        repo=repo,
        system_repo=system_repo,
        endpoint_uri=endpoint_uri,
        hierarchy_level=1,
        page=page,
        per_page=per_page,
        search_term=term,
    )
