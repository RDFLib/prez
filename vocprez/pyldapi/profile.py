from typing import List
from pydantic import AnyUrl, BaseModel


class Profile(BaseModel):
    uri: AnyUrl
    id: str
    label: str
    comment: str
    mediatypes: List[str]
    default_mediatype: str  # the ID of one of those in the mediatypes list of tuples
    languages: List[str]
    default_language: str
