import logging
import re

from pydantic import BaseModel


class ConnegpParser(BaseModel):
    headers: dict
    params: dict
    default_weighting: float = 1.0
    requested_profiles: list[tuple[str, float]] | None = None
    requested_mediatypes: list[tuple[str, float]] | None = None

    class Config:
        strict = False

    def _tupilize(self, string) -> tuple[str, float]:
        parts = string.split("q=")
        parts[0] = parts[0].strip(" ;<>")
        if len(parts) == 1:
            parts.append(self.default_weighting)
        else:
            try:
                parts[1] = float(parts[1])
            except ValueError as e:
                log = logging.getLogger("prez")
                log.debug(
                    f"Could not cast q={parts[1]} as float. Defaulting to {self.default_weighting}")
        return parts[0], parts[1]

    @staticmethod
    def _prioritize(types: list[tuple[str, float]]):
        return sorted(types, key=lambda x: x[1], reverse=True)

    def _parse_mediatypes(self) -> None:
        header_mediatypes: str = self.headers.get("Accept", "")
        qsa_mediatypes: str = self.params.get("_media", "")
        mediatypes = re.sub(r",$", "", "".join([qsa_mediatypes, header_mediatypes]))
        if mediatypes:
            mediatypes = [self._tupilize(mediatype) for mediatype in mediatypes.split(",")]
            self.requested_mediatypes = self._prioritize(mediatypes)

    def _parse_profiles(self) -> None:
        header_profiles: str = self.headers.get("Accept-Profile", "")
        qsa_profiles: str = self.params.get("_profile", "")
        profiles = re.sub(r",$", "", "".join([qsa_profiles, header_profiles]))
        if profiles:
            profiles = [self._tupilize(mediatype) for mediatype in profiles.split(",")]
            self.requested_profiles = self._prioritize(profiles)

    def get_requested_profiles(self) -> list[tuple[str, float]] | None:
        self._parse_profiles()
        return self.requested_profiles

    def get_requested_mediatypes(self) -> list[tuple[str, float]] | None:
        self._parse_mediatypes()
        return self.requested_mediatypes
