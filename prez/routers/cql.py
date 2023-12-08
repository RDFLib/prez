from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import URIRef

from prez.dependencies import (
    get_repo,
    cql_post_parser_dependency,
    get_system_repo,
    cql_get_parser_dependency,
)
from prez.services.listings import listing_function
from prez.sparql.methods import Repo

router = APIRouter(tags=["ogcrecords"])


@router.post(
    path="/cql",
    name="https://prez.dev/endpoint/cql-post",
)
async def cql_post_endpoint(
    request: Request,
    cql_parser: Optional[dict] = Depends(cql_post_parser_dependency),
    page: int = 1,
    per_page: int = 20,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    endpoint_uri = URIRef("https://prez.dev/endpoint/cql")
    return await listing_function(
        request=request,
        repo=repo,
        system_repo=system_repo,
        endpoint_uri=endpoint_uri,
        page=page,
        per_page=per_page,
        cql_parser=cql_parser,
    )


@router.get(
    path="/cql",
    name="https://prez.dev/endpoint/cql-get",
)
async def cql_get_endpoint(
    request: Request,
    cql_parser: Optional[dict] = Depends(cql_get_parser_dependency),
    page: int = 1,
    per_page: int = 20,
    repo: Repo = Depends(get_repo),
    system_repo: Repo = Depends(get_system_repo),
):
    endpoint_uri = URIRef("https://prez.dev/endpoint/cql")
    return await listing_function(
        request=request,
        repo=repo,
        system_repo=system_repo,
        endpoint_uri=endpoint_uri,
        page=page,
        per_page=per_page,
        cql_parser=cql_parser,
    )
