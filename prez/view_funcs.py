from typing import Optional

from async_lru import alru_cache
from fastapi import Request
from rdflib import Namespace

from prez.config import ENABLED_PREZS
from prez.profiles.generate_profiles import ProfileDetails
from prez.renderers import ProfilesRenderer


@alru_cache(maxsize=20)
async def profiles_func(request: Request, prez: Optional[str] = None):
    profiles_filenames = ["profiles.prez_profiles"]
    if prez == "VocPrez":
        profiles_filenames.append("profiles.vocprez_profiles")
    elif prez == "SpacePrez":
        profiles_filenames.append("profiles.spaceprez_profiles")
    elif prez is None:
        profiles_filenames.extend(
            [f"profiles.{p.lower()}_profiles" for p in ENABLED_PREZS]
        )
    else:
        raise Exception("invalid prez")

    PREZ = Namespace("https://surroundaustralia.com/prez/")

    instance_uri = str(
        request.url.remove_query_params(keys=request.query_params.keys())
    )
    profile_details = ProfileDetails(general_class=PREZ.Profiles, item_uri=instance_uri)
    await profile_details.get_all_profiles()

    profile_list = [dict(profile) for profile in profile_details.profiles_dict.values()]

    profiles_renderer = ProfilesRenderer(
        request,
        profile_details.profiles_dict,
        profile_details.default_profile,
        instance_uri,
        prez,
    )
    profiles_renderer.set_profiles(profile_list)
    return profiles_renderer.render()
