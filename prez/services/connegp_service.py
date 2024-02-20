import logging
import re

from pydantic import BaseModel


class TokenError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class ConnegpParser(BaseModel):
    """An implementation of the Content Negotiation by Profile Standard.
    See: https://w3c.github.io/dx-connegp/connegp/#introduction
    """
    headers: dict
    params: dict
    default_weighting: float = 1.0
    requested_profiles: list[tuple[str, float]] | None = None
    requested_mediatypes: list[tuple[str, float]] | None = None

    class Config:
        # Disabled to allow coercion of Starlette Headers and QueryParams to dict.
        strict = False

    @staticmethod
    def _resolve_token(token: str) -> str:
        # TODO: implement token resolution logic
        #       "there's a system_repo: Repo = Depends(get_system_repo)
        #       which you can SPARQL query to go from token -> uri"
        raise TokenError("Token Resolution not yet implemented")

    def _tupilize(self, string: str, is_profile: bool = False) -> tuple[str, float]:
        parts: list[str | float] = string.split("q=")  # split out the weighting
        parts[0] = parts[0].strip(" ;")  # remove the seperator character, and any whitespace characters
        if is_profile and not re.search(r"^<.*>$", parts[0]):  # If it doesn't look like a URI ...
            try:
                parts[0] = self._resolve_token(parts[0])  # then try to resolve the token to a URI
            except TokenError as e:
                log = logging.getLogger("prez")
                log.error(
                    f"Could not resolve URI for token '{parts[0]}': {e.args[0]}")
        if len(parts) == 1:
            parts.append(self.default_weighting)
        else:
            try:
                parts[1] = float(parts[1])  # Type-check the seperated weighting
            except ValueError as e:
                log = logging.getLogger("prez")
                log.debug(
                    f"Could not cast q={parts[1]} as float. Defaulting to {self.default_weighting}. {e.args[0]}")
        return parts[0], parts[1]

    @staticmethod
    def _prioritize(types: list[tuple[str, float]]) -> list[tuple[str, float]]:
        return sorted(types, key=lambda x: x[1], reverse=True)

    def _parse_mediatypes(self) -> None:
        raw_mediatypes: str = self.params.get("_media", "")  # Prefer mediatypes declared in the QSA, as per the spec.
        if not raw_mediatypes:
            raw_mediatypes: str = self.headers.get("Accept", "")
        if raw_mediatypes:
            mediatypes: list = [self._tupilize(mediatype) for mediatype in raw_mediatypes.split(",")]
            self.requested_mediatypes = self._prioritize(mediatypes)

    def _parse_profiles(self) -> None:
        raw_profiles: str = self.params.get("_profile", "")  # Prefer profiles declared in the QSA, as per the spec.
        if not raw_profiles:
            raw_profiles: str = self.headers.get("Accept-Profile", "")
        if raw_profiles:
            profiles: list = [self._tupilize(profile, is_profile=True) for profile in raw_profiles.split(",")]
            self.requested_profiles = self._prioritize(profiles)

    def get_requested_profiles(self) -> list[tuple[str, float]] | None:
        self._parse_profiles()
        return self.requested_profiles

    def get_requested_mediatypes(self) -> list[tuple[str, float]] | None:
        self._parse_mediatypes()
        return self.requested_mediatypes
