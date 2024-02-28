import logging
import re
from textwrap import dedent

from pydantic import BaseModel
from pyoxigraph import Store
from rdflib import Graph, Namespace, URIRef

from prez.cache import prefix_graph, system_store
from prez.dependencies import get_system_repo
from prez.models.model_exceptions import NoProfilesException
from prez.repositories.base import Repo
from prez.services.curie_functions import get_curie_id_for_uri

logger = logging.getLogger("prez")


class TokenError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class NegotiatedPMTs(BaseModel):
    """The Requested Profiles and Media Types as negotiated by the ConnegP standard.
    See: https://w3c.github.io/dx-connegp/connegp/#introduction

    Exposes the selected profile / media type as self.selected: dict
    with keys:
        - profile: URIRef
        - title: str
        - mediatype: str
        - class: str

    Response headers with alternate profiles / mediatypes can be generated by calling
    the .generate_response_headers() method.
    """
    headers: dict
    params: dict
    classes: list[URIRef]
    listing: bool = False
    default_weighting: float = 1.0
    requested_profiles: list[tuple[str, float]] | None = None
    requested_mediatypes: list[tuple[str, float]] | None = None
    available: list[dict] | None = None
    selected: dict | None = None
    _system_store: Store | None = None
    _prefix_graph: Graph | None = None
    _system_repo: Repo | None = None

    class Config:
        arbitrary_types_allowed = True

    async def setup(self) -> bool:
        if self._system_store is None:
            self._system_store = system_store
        if self._prefix_graph is None:
            self._prefix_graph = prefix_graph
        if self._system_repo is None:
            self._system_repo = await get_system_repo(self._system_store)
        self.requested_profiles = await self._get_requested_profiles()
        self.requested_mediatypes = await self._get_requested_mediatypes()
        self.available = await self._get_available()
        self.selected = await self._get_selected()
        return True if self.selected else False

    async def _resolve_token(self, token: str) -> str:
        query_str: str = dedent("""
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
    
        SELECT ?s
        WHERE {
            ?s a prof:Profile .
            ?s dcterms:identifier ?o .
            FILTER(?o="<token>"^^xsd:token)
        }
        """.replace("<token>", token))
        try:
            result = {result[0].value for result in self._system_store.query(query_str)}.pop()  # TODO: use _system_repo.send_queries instead
        except KeyError:
            raise TokenError(f"Token: '{token}' could not be resolved to URI")
        uri = "<" + result + ">"
        return uri

    async def _tupilize(self, string: str, is_profile: bool = False) -> tuple[str, float]:
        parts: list[str | float] = string.split("q=")  # split out the weighting
        parts[0] = parts[0].strip(" ;")  # remove the seperator character, and any whitespace characters
        if is_profile and not re.search(r"^<.*>$", parts[0]):  # If it doesn't look like a URI ...
            try:
                parts[0] = await self._resolve_token(parts[0])  # then try to resolve the token to a URI
            except TokenError as e:
                logger.error(e.args[0])
                try:  # if token resolution fails, try to resolve as a curie
                    result = str(self._prefix_graph.namespace_manager.expand_curie(parts[0]))
                    parts[0] = "<" + result + ">"
                except ValueError as e:
                    logger.error(e.args[0])
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

    async def _get_requested_profiles(self) -> list[tuple[str, float]] | None:
        raw_profiles: str = self.params.get("_profile", "")  # Prefer profiles declared in the QSA, as per the spec.
        if not raw_profiles:
            raw_profiles: str = self.headers.get("accept-profile", "")
        if raw_profiles:
            profiles: list = [await self._tupilize(profile, is_profile=True) for profile in raw_profiles.split(",")]
            return self._prioritize(profiles)
        return None

    async def _get_requested_mediatypes(self) -> list[tuple[str, float]] | None:
        raw_mediatypes: str = self.params.get("_media", "")  # Prefer mediatypes declared in the QSA, as per the spec.
        if not raw_mediatypes:
            raw_mediatypes: str = self.headers.get("accept", "")
        if raw_mediatypes:
            mediatypes: list = [await self._tupilize(mediatype) for mediatype in raw_mediatypes.split(",")]
            return self._prioritize(mediatypes)
        return None

    async def _get_available(self) -> list[dict]:
        query = self._compose_select_query()
        repo_response = await self._do_query(query)
        available = [
            {
                "profile": URIRef(result["profile"]["value"]),
                "title": result["title"]["value"],
                "mediatype": result["format"]["value"],
                "class": result["class"]["value"]
            } for result in repo_response[1][0][1]
        ]
        return available

    async def _get_selected(self) -> dict:
        return self.available[0]

    def generate_response_headers(self) -> dict:
        profile_uri = "<http://www.w3.org/ns/dx/prof/Profile>"
        distinct_profiles = {(pmt["profile"], pmt["title"]) for pmt in self.available}
        profile_header_links = ", ".join(
            [f'<{self.selected["profile"]}>; rel="profile"'] +
            [
                f'{profile_uri}; rel="type"; title="{pmt[1]}"; token="{get_curie_id_for_uri(pmt[0])}"; anchor={pmt[0]}"'
                for pmt in distinct_profiles
            ]
        )
        mediatype_header_links = ", ".join(
            [
                f'<{self.selected["class"]}?_profile={get_curie_id_for_uri(pmt["profile"])}&_mediatype={pmt["mediatype"]}>; rel="{"self" if pmt == self.selected else "alternate"}"; type="{pmt["mediatype"]}"; profile="{pmt["profile"]}"'
                for pmt in self.available
            ]
        )
        headers = {
            "Content-Type": self.selected["mediatype"],
            "link": profile_header_links + mediatype_header_links
        }
        return headers

    def _compose_select_query(self) -> str:
        prez = Namespace("https://prez.dev/")
        profile_class = prez.ListingProfile if self.listing else prez.ObjectProfile
        try:
            requested_profile = self.requested_profiles[0]  # TODO: handle multiple requested profiles
        except TypeError as e:
            requested_profile = None
            logger.debug(e)

        query = dedent(
            f"""
            PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX geo: <http://www.opengis.net/ont/geosparql#>
            PREFIX prez: <https://prez.dev/>
            PREFIX prof: <http://www.w3.org/ns/dx/prof/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX sh: <http://www.w3.org/ns/shacl#>
        
            SELECT ?profile ?title ?class (count(?mid) as ?distance) ?req_profile ?def_profile ?format ?req_format ?def_format
        
            WHERE {{
              VALUES ?class {{{" ".join('<' + str(klass) + '>' for klass in self.classes)}}}
              ?class rdfs:subClassOf* ?mid .
              ?mid rdfs:subClassOf* ?base_class .
              VALUES ?base_class {{ dcat:Dataset geo:FeatureCollection geo:Feature
              skos:ConceptScheme skos:Concept skos:Collection 
              dcat:Catalog dcat:Resource prof:Profile prez:SPARQLQuery 
              prez:SearchResult prez:CQLObjectList prez:QueryablesList prez:Object }}
              ?profile altr-ext:constrainsClass ?class ;
                       altr-ext:hasResourceFormat ?format ;
                       dcterms:title ?title .\
              {f'?profile a {profile_class.n3()} .'}
              {f'BIND(?profile=<{requested_profile}> as ?req_profile)' if requested_profile else ''}
              BIND(EXISTS {{ ?shape sh:targetClass ?class ;
                                   altr-ext:hasDefaultProfile ?profile }} AS ?def_profile)
              {self._generate_mediatype_if_statements()}
              BIND(EXISTS {{ ?profile altr-ext:hasDefaultResourceFormat ?format }} AS ?def_format)
            }}
            GROUP BY ?class ?profile ?req_profile ?def_profile ?format ?req_format ?def_format ?title
            ORDER BY DESC(?req_profile) DESC(?distance) DESC(?def_profile) DESC(?req_format) DESC(?def_format)
            """
        )

        logger.debug(f"ConnegP query: {query}")
        return query

    def _generate_mediatype_if_statements(self) -> str:
        """
        Generates a list of if statements used to determine the response mediatype based on user requests,
        and the availability of these in profiles.
        These are of the form:
          BIND(
            IF(?format="application/ld+json", "0.9",
              IF(?format="text/html", "0.8",
                IF(?format="image/apng", "0.7", ""))) AS ?req_format)
        """
        if not self.requested_mediatypes:
            return ""
        line_join = "," + "\n"
        ifs = (
            f"BIND(\n"
            f"""{line_join.join(
                {chr(9) + 'IF(?format="' + tup[0] + '", "' + str(tup[1]) + '"' for tup in self.requested_mediatypes}
            )}"""
            f""", ""{')' * len(self.requested_mediatypes)}\n"""
            f"\tAS ?req_format)"
        )
        return ifs

    async def _do_query(self, query: str) -> tuple[Graph, list]:
        response = await self._system_repo.send_queries([], [(None, query)])
        if not response[1][0][1]:
            raise NoProfilesException(self.classes)
        return response
