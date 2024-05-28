# from typing import Optional
#
# from fastapi import APIRouter, Request, Depends
# from rdflib import Namespace
# from rdflib.namespace import URIRef
#
# from prez.dependencies import (
#     get_data_repo,
#     cql_post_parser_dependency,
#     get_system_repo,
#     cql_get_parser_dependency,
# )
# from prez.reference_data.prez_ns import PREZ
# from prez.repositories import Repo
#
# router = APIRouter(tags=["ogcrecords"])
#
# OGCE = Namespace(PREZ["endpoint/extended-ogc-records/"])
#
#
# @router.post(
#     path="/cql",
#     name=OGCE["cql-post"],
# )
# async def cql_post_endpoint(
#     request: Request,
#     cql_parser: Optional[dict] = Depends(cql_post_parser_dependency),
#     page: int = 1,
#     per_page: int = 20,
#     repo: Repo = Depends(get_data_repo),
#     system_repo: Repo = Depends(get_system_repo),
# ):
#     endpoint_uri = URIRef("https://prez.dev/endpoint/cql/post")
#     return await listing_function(
#         request=request,
#         repo=repo,
#         system_repo=system_repo,
#         endpoint_uri=endpoint_uri,
#         page=page,
#         per_page=per_page,
#         cql_parser=cql_parser,
#     )
#
#
# @router.get(
#     path="/cql",
#     name=OGCE["cql-get"],
# )
# async def cql_get_endpoint(
#     request: Request,
#     cql_parser: Optional[dict] = Depends(cql_get_parser_dependency),
#     page: int = 1,
#     per_page: int = 20,
#     repo: Repo = Depends(get_data_repo),
#     system_repo: Repo = Depends(get_system_repo),
# ):
#     endpoint_uri = URIRef("https://prez.dev/endpoint/cql/get")
#     return await listing_function(
#         request=request,
#         repo=repo,
#         system_repo=system_repo,
#         hierarchy_level=1,
#         endpoint_uri=endpoint_uri,
#         page=page,
#         per_page=per_page,
#         cql_parser=cql_parser,
#     )
#
#
# @router.get(
#     path="/queryables",
#     name=OGCE["cql-queryables"],
# )
# async def queryables_endpoint(
#     request: Request,
#     cql_parser: Optional[dict] = Depends(cql_get_parser_dependency),
#     page: int = 1,
#     per_page: int = 20,
#     repo: Repo = Depends(get_data_repo),
#     system_repo: Repo = Depends(get_system_repo),
# ):
#     endpoint_uri = URIRef(request.scope.get("route").name)
#     return await listing_function(
#         request=request,
#         repo=repo,
#         system_repo=system_repo,
#         endpoint_uri=endpoint_uri,
#         hierarchy_level=1,
#         page=page,
#         per_page=per_page,
#         cql_parser=cql_parser,
#     )
