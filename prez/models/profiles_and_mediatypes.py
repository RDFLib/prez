from typing import FrozenSet, Optional

from pydantic import BaseModel, model_validator
from rdflib import Namespace, URIRef
from starlette.requests import Request

from prez.services.generate_profiles import get_profiles_and_mediatypes
from prez.services.connegp_service import get_requested_profile_and_mediatype

PREZ = Namespace("https://prez.dev/")


class ProfilesMediatypesInfo(BaseModel):
    class Config:
        arbitrary_types_allowed = True

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

    @model_validator(mode="after")
    def populate_requested_types(self):
        request = self.request
        (
            self.req_profiles,
            self.req_profiles_token,
            self.req_mediatypes,
        ) = get_requested_profile_and_mediatype(request)
        return self

    @model_validator(mode="after")
    def populate_profile_and_mediatype(self):
        req_profiles = self.req_profiles
        req_profiles_token = self.req_profiles_token
        req_mediatypes = self.req_mediatypes
        classes = self.classes
        (
            self.profile,
            self.mediatype,
            self.selected_class,
            self.profile_headers,
            self.avail_profile_uris,
        ) = get_profiles_and_mediatypes(
            classes, req_profiles, req_profiles_token, req_mediatypes
        )
        return self
