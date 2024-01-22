from typing import FrozenSet, Optional

from pydantic import BaseModel, model_validator
from rdflib import Namespace, URIRef
from starlette.requests import Request

from prez.services.generate_profiles import get_profiles_and_mediatypes
from prez.services.connegp_service import get_requested_profile_and_mediatype
from prez.sparql.methods import Repo

PREZ = Namespace("https://prez.dev/")


class ProfilesMediatypesInfo(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    request: Request  # TODO slim down once connegp is refactored so the whole request doesn't need to be passed through
    classes: FrozenSet[URIRef]
    system_repo: Repo
    req_profiles: Optional[str] = None
    req_profiles_token: Optional[str] = None
    req_mediatypes: Optional[FrozenSet] = None
    profile: Optional[URIRef] = None
    mediatype: Optional[str] = None
    selected_class: Optional[URIRef] = None
    profile_headers: Optional[str] = None
    avail_profile_uris: Optional[str] = None
    listing: Optional[bool] = False

    @model_validator(mode="after")
    def populate_requested_types(self):
        request = self.request
        (
            self.req_profiles,
            self.req_profiles_token,
            self.req_mediatypes,
        ) = get_requested_profile_and_mediatype(request)
        return self

async def populate_profile_and_mediatype(
        profiles_mediatypes_model: ProfilesMediatypesInfo,
        system_repo: Repo
):
    req_profiles = profiles_mediatypes_model.req_profiles
    req_profiles_token = profiles_mediatypes_model.req_profiles_token
    req_mediatypes = profiles_mediatypes_model.req_mediatypes
    classes = profiles_mediatypes_model.classes
    listing = profiles_mediatypes_model.listing
    (
        profiles_mediatypes_model.profile,
        profiles_mediatypes_model.mediatype,
        profiles_mediatypes_model.selected_class,
        profiles_mediatypes_model.profile_headers,
        profiles_mediatypes_model.avail_profile_uris,
    ) = await get_profiles_and_mediatypes(
        classes, system_repo, req_profiles, req_profiles_token, req_mediatypes, listing
    )