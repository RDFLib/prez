from fastapi import APIRouter, Request, Depends

from prez.dependencies import get_system_repo
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.listings import listing_function
from prez.services.objects import object_function
from rdflib import URIRef

router = APIRouter(tags=["Profiles"])


@router.get(
    "/profiles",
    summary="List Profiles",
    name="https://prez.dev/endpoint/system/profiles-listing",
)
@router.get(
    "/s/profiles",
    summary="SpacePrez Profiles",
    name="https://prez.dev/endpoint/system/spaceprez-profiles-listing",
)
@router.get(
    "/v/profiles",
    summary="VocPrez Profiles",
    name="https://prez.dev/endpoint/system/vocprez-profiles-listing",
)
@router.get(
    "/c/profiles",
    summary="CatPrez Profiles",
    name="https://prez.dev/endpoint/system/catprez-profiles-listing",
)
async def profiles(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    repo=Depends(get_system_repo),
):
    endpoint_uri = URIRef(request.scope.get("route").name)
    return await listing_function(
        request=request,
        repo=repo,
        system_repo=repo,
        endpoint_uri=endpoint_uri,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/profiles/{profile_curie}",
    summary="Profile",
    name="https://prez.dev/endpoint/system/profile-object",
)
async def profile(request: Request, profile_curie: str, repo=Depends(get_system_repo)):
    request_url = request.scope["path"]
    endpoint_uri = URIRef(request.scope.get("route").name)
    profile_uri = get_uri_for_curie_id(profile_curie)
    return await object_function(
        request=request,
        endpoint_uri=endpoint_uri,
        uri=profile_uri,
        request_url=request_url,
        repo=repo,
        system_repo=repo,
    )
