import logging
from functools import lru_cache
from pathlib import Path
from typing import FrozenSet

from rdflib import Graph, URIRef

from prez.cache import profiles_graph_cache
from prez.config import settings
from prez.sparql.methods import sparql_construct
from prez.sparql.objects_listings import select_profile_mediatype

log = logging.getLogger(__name__)


async def create_profiles_graph() -> Graph:
    if (
        len(profiles_graph_cache) > 0
    ):  # pytest imports app.py multiple times, so this is needed. Not sure why cache is
        # not cleared between calls
        return
    for f in (Path(__file__).parent.parent / "reference_data/profiles").glob("*.ttl"):
        profiles_graph_cache.parse(f)
    log.info("Prez default profiles loaded")
    remote_profiles_query = """
        PREFIX dcat: <http://www.w3.org/ns/dcat#>
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        CONSTRUCT {?s ?p ?o .
                    ?o ?p2 ?o2 .
                    ?o2 ?p3 ?o3 .
                    ?class ?cp ?co}
        WHERE {?s a prof:Profile ;
                      ?p ?o
          OPTIONAL {?o ?p2 ?o2
            FILTER(ISBLANK(?o))
            OPTIONAL {?o2 ?p3 ?o3
            FILTER(ISBLANK(?o2))}
          }
          OPTIONAL {
            ?class rdfs:subClassOf dcat:Resource ;
                ?cp ?co .
          }
          OPTIONAL {
            ?class rdfs:subClassOf geo:Feature ;
                ?cp ?co .
          }
          OPTIONAL {
            ?class rdfs:subClassOf skos:Concept ;
                ?cp ?co .
          }
        }
        """
    any_remote_profiles = False
    for p in settings.enabled_prezs:
        r = await sparql_construct(remote_profiles_query, p)
        if r[0] and r[1]:
            any_remote_profiles = True
            profiles_graph_cache.__iadd__(r[1])
            log.info(f"Remote profiles found and added for {p}")
    if not any_remote_profiles:
        log.info("No remote profiles found")


@lru_cache(maxsize=128)
def get_profiles_and_mediatypes(
    classes: FrozenSet[URIRef],
    requested_profile: URIRef = None,
    requested_profile_token: str = None,
    requested_mediatype: URIRef = None,
):
    query = select_profile_mediatype(
        classes, requested_profile, requested_profile_token, requested_mediatype
    )
    response = profiles_graph_cache.query(query)
    if len(response.bindings[0]) == 0:
        raise ValueError(
            f"No profiles and/or mediatypes could be found to render the resource. The resource class(es) searched for "
            f"were: {', '.join(klass for klass in classes)}"
        )
    top_result = response.bindings[0]
    profile, mediatype, selected_class = (
        top_result["profile"],
        top_result["format"],
        top_result["class"],
    )
    profile_headers, avail_profile_uris = generate_profiles_headers(
        selected_class, response, profile, mediatype
    )
    return profile, mediatype, selected_class, profile_headers, avail_profile_uris


def generate_profiles_headers(selected_class, response, profile, mediatype):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": mediatype,
    }
    avail_profiles = set(
        (i["token"], i["profile"], i["title"]) for i in response.bindings
    )
    avail_profiles_headers = ", ".join(
        [
            f'<http://www.w3.org/ns/dx/prof/Profile>; rel="type"; title="{i[2]}"; token="{i[0]}"; anchor=<{i[1]}>'
            for i in avail_profiles
        ]
    )
    avail_mediatypes_headers = ", ".join(
        [
            f"""<{selected_class}?_profile={i["token"]}&_mediatype={i["format"]}>; \
rel="{"self" if i["profile"] == profile and i["format"] == mediatype else "alternate"}"; \
type="{i["format"]}"; profile="{i["profile"]}"\
"""
            for i in response.bindings
        ]
    )
    headers["Link"] = ", ".join(
        [
            f'<{profile}>; rel="profile"',
            avail_profiles_headers,
            avail_mediatypes_headers,
        ]
    )
    avail_profile_uris = [i[1] for i in avail_profiles]
    return headers, avail_profile_uris
