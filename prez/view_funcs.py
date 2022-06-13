from typing import Optional

from fastapi import Request
from connegp import Profile

from renderers import ProfilesRenderer
from config import ENABLED_PREZS


async def profiles_func(request: Request, prez: Optional[str] = None):
    profiles_filenames = ["profiles.prez_profiles"]
    if prez == "vocprez":
        profiles_filenames.append("profiles.vocprez_profiles")
    elif prez == "spaceprez":
        profiles_filenames.append("profiles.spaceprez_profiles")
    elif prez is None:
        profiles_filenames.extend([f"profiles.{p.lower()}_profiles" for p in ENABLED_PREZS])
    else:
        raise Exception("invalid prez")

    import importlib

    profiles = [importlib.import_module(file) for file in profiles_filenames]

    # get distinct list of profiles
    profile_list = []
    for file in profiles:
        for item in dir(file):
            if not item.startswith("__") and not item == "profiles":
                profile = getattr(file, item)
                if isinstance(profile, Profile) and dict(profile) not in profile_list:
                    profile_list.append(dict(profile))
    profile_list.sort(key=lambda p: p["id"])

    profiles_renderer = ProfilesRenderer(
        request, str(request.url.remove_query_params(keys=request.query_params.keys())), prez
    )
    profiles_renderer.set_profiles(profile_list)
    return profiles_renderer.render()
