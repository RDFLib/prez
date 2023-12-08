import logging
from pathlib import Path
from typing import FrozenSet

from rdflib import Graph, URIRef, RDF, PROF, Literal

from prez.cache import profiles_graph_cache, prefix_graph
from prez.config import settings
from prez.models.model_exceptions import NoProfilesException
from prez.reference_data.prez_ns import PREZ
from prez.services.curie_functions import get_curie_id_for_uri
from prez.sparql.objects_listings import select_profile_mediatype

log = logging.getLogger(__name__)


async def create_profiles_graph(repo) -> Graph:
    if (
        len(profiles_graph_cache) > 0
    ):  # pytest imports app.py multiple times, so this is needed. Not sure why cache is
        # not cleared between calls
        return
    flavours = ["CatPrez", "SpacePrez", "VocPrez"]
    for f in (Path(__file__).parent.parent / "reference_data/profiles").glob("*.ttl"):
        # Check if file starts with any of the flavour prefixes
        matching_flavour = next(
            (flavour for flavour in flavours if f.name.startswith(flavour.lower())),
            None,
        )
        # If the file doesn't start with any specific flavour or the matching flavour is in settings.prez_flavours, parse it.
        if not matching_flavour or (
            matching_flavour and matching_flavour in settings.prez_flavours
        ):
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
    g, _ = await repo.send_queries([remote_profiles_query], [])
    if len(g) > 0:
        profiles_graph_cache.__iadd__(g)
        log.info(f"Remote profile(s) found and added")
    else:
        log.info("No remote profiles found")
    # add profiles internal links
    _add_prez_profile_links()


# @lru_cache(maxsize=128)
def get_profiles_and_mediatypes(
    classes: FrozenSet[URIRef],
    requested_profile: URIRef = None,
    requested_profile_token: str = None,
    requested_mediatype: URIRef = None,
):
    query = select_profile_mediatype(
        classes, requested_profile, requested_profile_token, requested_mediatype
    )
    log.debug(f"ConnegP query: {query}")
    response = profiles_graph_cache.query(query)
    # log.debug(f"ConnegP response:{results_pretty_printer(response)}")
    if len(response.bindings[0]) == 0:
        raise NoProfilesException(classes)
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


def results_pretty_printer(response):
    # Calculate max width for each column, including the new "#" column
    max_widths = [
        len(str(len(response.bindings)))
    ]  # length of the highest row number as a string
    for header in response.vars:
        max_width = max(
            len(header.n3(prefix_graph.namespace_manager)),
            max(
                len(
                    row[header].n3(prefix_graph.namespace_manager)
                    if row[header]
                    else ""
                )
                for row in response.bindings
            ),
        )
        max_widths.append(max_width)

    # Header row
    header_row = "\n" + " | ".join(
        ["#".ljust(max_widths[0])]
        + [
            str(header).ljust(max_widths[i + 1])
            for i, header in enumerate(response.vars)
        ]
    )
    pp_string = header_row + "\n"
    pp_string += ("-" * len(header_row)) + "\n"  # Divider

    # Data rows
    row_number = 1
    for row in response.bindings:
        row_data = [str(row_number).ljust(max_widths[0])]
        row_data += [
            (
                row[header].n3(prefix_graph.namespace_manager) if row[header] else ""
            ).ljust(max_widths[i + 1])
            for i, header in enumerate(response.vars)
        ]
        formatted_row = " | ".join(row_data)
        pp_string += formatted_row + "\n"
        row_number += 1

    return pp_string


def generate_profiles_headers(selected_class, response, profile, mediatype):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": mediatype,
    }
    avail_profiles = set(
        (get_curie_id_for_uri(i["profile"]), i["profile"], i["title"])
        for i in response.bindings
    )
    avail_profiles_headers = ", ".join(
        [
            f'<http://www.w3.org/ns/dx/prof/Profile>; rel="type"; title="{i[2]}"; token="{i[0]}"; anchor=<{i[1]}>'
            for i in avail_profiles
        ]
    )
    avail_mediatypes_headers = ", ".join(
        [
            f"""<{selected_class}?_profile={get_curie_id_for_uri(i["profile"])}&_mediatype={i["format"]}>; \
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


def _add_prez_profile_links():
    for profile in profiles_graph_cache.subjects(
        predicate=RDF.type, object=PROF.Profile
    ):
        profiles_graph_cache.add(
            (
                profile,
                PREZ["link"],
                Literal(f"/profiles/{get_curie_id_for_uri(profile)}"),
            )
        )
    # profiles_graph_cache.__iadd__(g)
