from fastapi import APIRouter, Request

from prez.routers.object import listing_function, item_function

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
):
    return await listing_function(request, page, per_page)


@router.get(
    "/profiles/{profile_curie}",
    summary="Profile",
    name="https://prez.dev/endpoint/profile",
)
async def profile(request: Request, profile_curie: str):
    return await item_function(request, object_curie=profile_curie)
