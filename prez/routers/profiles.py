from fastapi import APIRouter, Request, Depends

from prez.dependencies import get_query_sender
from prez.services.objects import object_function
from prez.services.listings import listing_function

router = APIRouter(tags=["Profiles"])


@router.get(
    "/profiles",
    summary="List Profiles",
    name="https://prez.dev/endpoint/profiles-listing",
)
@router.get(
    "/s/profiles",
    summary="SpacePrez Profiles",
    name="https://prez.dev/endpoint/spaceprez-profiles-listing",
)
@router.get(
    "/v/profiles",
    summary="VocPrez Profiles",
    name="https://prez.dev/endpoint/vocprez-profiles-listing",
)
@router.get(
    "/c/profiles",
    summary="CatPrez Profiles",
    name="https://prez.dev/endpoint/catprez-profiles-listing",
)
async def profiles(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    query_sender=Depends(get_query_sender),
):
    return await listing_function(
        request=request, page=page, per_page=per_page, query_sender=query_sender
    )


@router.get(
    "/profiles/{profile_curie}",
    summary="Profile",
    name="https://prez.dev/endpoint/profile",
)
async def profile(
    request: Request, profile_curie: str, query_sender=Depends(get_query_sender)
):
    return await object_function(
        request, object_curie=profile_curie, query_sender=query_sender
    )
