from typing import Optional

from fastapi import Request
from connegp import Profile

from renderers import ProfilesRenderer


async def profiles_func(request: Request, prez: Optional[str] = None):
    profiles_filename = ""
    if prez == "VocPrez":
        profiles_filename = "profiles"
    import importlib

    profiles = importlib.import_module(profiles_filename)

    profiles_renderer = ProfilesRenderer(
        request, str(request.url.remove_query_params(keys=request.query_params.keys()))
    )

    # get list of profiles from profiles.py
    profile_list = []
    for item in dir(profiles):
        if not item.startswith("__") and not item == "profiles":
            profile = getattr(profiles, item)
            if isinstance(profile, Profile):
                profile_list.append(dict(profile))
    profile_list.sort(key=lambda p: p["id"])
    profiles_renderer.set_profiles(profile_list)
    return profiles_renderer.render()
