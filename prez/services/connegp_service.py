import logging
import re

from pydantic import BaseModel
from pyoxigraph import Store
from rdflib import Graph

from prez.cache import system_store, prefix_graph
from prez.services.curie_functions import get_uri_for_curie_id


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
    system_store: Store | None = None  # facilitate tests overriding the system_store
    prefix_graph: Graph | None = None  # facilitate tests overriding the prefix_graph
    requested_profiles: list[tuple[str, float]] | None = None
    requested_mediatypes: list[tuple[str, float]] | None = None

    class Config:
        strict = False
        arbitrary_types_allowed = True

    def _resolve_token(self, token: str) -> str:
        query_str: str = """
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
        
        SELECT ?s
        WHERE {
            ?s a prof:Profile .
            ?s dcterms:identifier ?o .
            FILTER(?o="<token>"^^xsd:token)
        }
        """.replace("<token>", token)
        if self.system_store is None:
            self.system_store = system_store
        try:
            result = {result[0].value for result in self.system_store.query(query_str)}.pop()
        except KeyError:
            raise TokenError(f"Token: '{token}' could not be resolved to URI")
        uri = "<" + result + ">"
        return uri

    def _tupilize(self, string: str, is_profile: bool = False) -> tuple[str, float]:
        parts: list[str | float] = string.split("q=")  # split out the weighting
        parts[0] = parts[0].strip(" ;")  # remove the seperator character, and any whitespace characters
        if is_profile and not re.search(r"^<.*>$", parts[0]):  # If it doesn't look like a URI ...
            try:
                parts[0] = self._resolve_token(parts[0])  # then try to resolve the token to a URI
            except TokenError as e:
                log = logging.getLogger("prez")
                log.error(e.args[0])
                try:  # if token resolution fails, try to resolve as a curie
                    if self.prefix_graph is None:
                        self.prefix_graph = prefix_graph
                    result = str(self.prefix_graph.namespace_manager.expand_curie(parts[0]))
                    parts[0] = "<" + result + ">"
                except ValueError as e:
                    log.error(e.args[0])
        if len(parts) == 1:
            parts.append(self.default_weighting)  # If no weight given, set the default
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
