from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import URIRef

from prez.dependencies import get_repo, cql_parser_dependency
from prez.services.listings import listing_function_new
from prez.sparql.methods import Repo

router = APIRouter(tags=["ogcrecords"])


@router.post(
    path="/cql",
    name="https://prez.dev/endpoint/cql",
)
async def cql_post_endpoint(
    request: Request,
    parsed_cql: Optional[dict] = Depends(cql_parser_dependency),
    page: int = 1,
    per_page: int = 20,
    repo: Repo = Depends(get_repo),
):
    endpoint_uri = URIRef("https://prez.dev/endpoint/cql")
    return await listing_function_new(
        request, repo, endpoint_uri, page, per_page, parsed_cql
    )
