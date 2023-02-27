import time

from connegp import Connegp
from fastapi import Request


def get_requested_profile_and_mediatype(request: Request):
    """Return the requested profile and mediatype."""

    c = Connegp(request)
    return (
        c.profile_uris_requested,
        c.profile_tokens_requested,
        frozenset(c.mediatypes_requested),
    )
