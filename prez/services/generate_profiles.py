import logging
from pathlib import Path
from typing import FrozenSet

from rdflib import Graph, URIRef, RDF, PROF, Literal

from prez.cache import profiles_graph_cache, prefix_graph
from prez.models.model_exceptions import NoProfilesException
from prez.reference_data.prez_ns import PREZ
from prez.services.curie_functions import get_curie_id_for_uri
from prez.repositories import Repo
from prez.services.query_generation.connegp import select_profile_mediatype

log = logging.getLogger(__name__)


async def create_profiles_graph(repo) -> Graph:
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
    g, _ = await repo.send_queries([remote_profiles_query], [])
    if len(g) > 0:
        profiles_graph_cache.__iadd__(g)
        log.info(f"Remote profile(s) found and added")
    else:
        log.info("No remote profiles found")


async def get_profiles_and_mediatypes(
    classes: FrozenSet[URIRef],
    system_repo: Repo,
    requested_profile: URIRef = None,
    requested_profile_token: str = None,
    requested_mediatype: URIRef = None,
    listing: bool = False,
):
    query = select_profile_mediatype(
        classes,
        requested_profile,
        requested_profile_token,
        requested_mediatype,
        listing,
    )
    log.debug(f"ConnegP query: {query}")
    # response = profiles_graph_cache.query(query)
    response = await system_repo.send_queries([], [(None, query)])
    # log.debug(f"ConnegP response:{results_pretty_printer(response)}")
    if response[1][0][1] == []:
        raise NoProfilesException(classes)
    top_result = response[1][0][1][0]
    profile, mediatype, selected_class = (
        URIRef(top_result["profile"]["value"]),
        Literal(top_result["format"]["value"]),
        URIRef(top_result["class"]["value"]),
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
        (
            get_curie_id_for_uri(i["profile"]["value"]),
            i["profile"]["value"],
            i["title"]["value"],
        )
        for i in response[1][0][1]
    )
    avail_profiles_headers = ", ".join(
        [
            f'<http://www.w3.org/ns/dx/prof/Profile>; rel="type"; title="{i[2]}"; token="{i[0]}"; anchor=<{i[1]}>'
            for i in avail_profiles
        ]
    )
    avail_mediatypes_headers = ", ".join(
        [
            f"""<{selected_class}?_profile={get_curie_id_for_uri(i["profile"]["value"])}&_mediatype={i["format"]["value"]}>; \
rel="{"self" if i["profile"]["value"] == profile and i["format"]["value"] == mediatype else "alternate"}"; \
type="{i["format"]["value"]}"; profile="{i["profile"]["value"]}"\
"""
            for i in response[1][0][1]
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
