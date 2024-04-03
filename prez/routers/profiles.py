from typing import Optional

from fastapi import APIRouter, Request, Depends
from rdflib import URIRef

from prez.dependencies import get_system_repo, get_endpoint_nodeshapes, get_negotiated_pmts, get_profile_nodeshape, \
    cql_get_parser_dependency, generate_search_query, get_data_repo
from prez.repositories import Repo
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function_new
from prez.services.objects import object_function
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.shacl import NodeShape
from temp.grammar import ConstructQuery

router = APIRouter(tags=["Profiles"])


# @router.get(
#     "/profiles",
#     summary="List Profiles",
#     name="https://prez.dev/endpoint/system/profile-listing",
# )
# async def profiles(
#     request: Request,
#     page: int = 1,
#     per_page: int = 20,
#     repo=Depends(get_system_repo),
# ):
#     endpoint_uri = URIRef(request.scope.get("route").name)
#     return await listing_function(
#         request=request,
#         repo=repo,
#         system_repo=repo,
#         endpoint_uri=endpoint_uri,
#         hierarchy_level=1,
#         page=page,
#         per_page=per_page,
#         endpoint_structure=("profiles",),
#     )


# @router.get(
#     "/profiles/{profile_curie}",
#     summary="Profile",
#     name="https://prez.dev/endpoint/system/profile-object",
# )
# async def profile(request: Request, profile_curie: str, repo=Depends(get_system_repo)):
#     request_url = request.scope["path"]
#     endpoint_uri = URIRef(request.scope.get("route").name)
#     profile_uri = await get_uri_for_curie_id(profile_curie)
#     return await object_function(
#         request=request,
#         endpoint_uri=endpoint_uri,
#         uri=profile_uri,
#         request_url=request_url,
#         repo=repo,
#         system_repo=repo,
#     )
