from typing import FrozenSet, Optional

from pydantic import BaseModel, root_validator
from rdflib import Namespace, URIRef
from starlette.requests import Request

from prez.services.generate_profiles import get_profiles_and_mediatypes
from prez.services.connegp_service import get_requested_profile_and_mediatype

PREZ = Namespace("https://prez.dev/")


class ProfilesMediatypesInfo(BaseModel):
    request: Request  # TODO slim down once connegp is refactored so the whole request doesn't need to be passed through
    classes: FrozenSet[URIRef]
    req_profiles: Optional[str] = None
    req_profiles_token: Optional[str] = None
    req_mediatypes: Optional[FrozenSet] = None
    profile: Optional[URIRef] = None
    mediatype: Optional[str] = None
    selected_class: Optional[URIRef] = None
    profile_headers: Optional[str] = None
    avail_profile_uris: Optional[str] = None

    @root_validator
    def populate_requested_types(cls, values):
        request = values.get("request")
        (
            values["req_profiles"],
            values["req_profiles_token"],
            values["req_mediatypes"],
        ) = get_requested_profile_and_mediatype(request)
        return values

    @root_validator
    def populate_profile_and_mediatype(cls, values):
        req_profiles = values.get("req_profiles")
        req_profiles_token = values.get("req_profiles_token")
        req_mediatypes = values.get("req_mediatypes")
        classes = values.get("classes")
        (
            values["profile"],
            values["mediatype"],
            values["selected_class"],
            values["profile_headers"],
            values["avail_profile_uris"],
        ) = get_profiles_and_mediatypes(
            classes, req_profiles, req_profiles_token, req_mediatypes
        )
        return values
