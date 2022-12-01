import logging
from functools import lru_cache
from pathlib import Path
from typing import List

from rdflib import Graph, URIRef

from prez.cache import profiles_graph_cache
from prez.services.sparql_new import select_profile_mediatype
from prez.services.sparql_utils import (
    sparql_construct_non_async,
)


def create_profiles_graph(ENABLED_PREZS) -> Graph:
    if (
        len(profiles_graph_cache) > 0
    ):  # pytest imports app.py multiple times, so this is needed. Not sure why cache is
        # not cleared between calls
        return
    for f in Path(__file__).parent.glob("*.ttl"):
        profiles_graph_cache.parse(f)
    logging.info("Loaded local profiles")

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

    for p in ENABLED_PREZS:
        r = sparql_construct_non_async(remote_profiles_query, p)
        if r[0]:
            profiles_graph_cache.__add__(r[1])
            logging.info(f"Also using remote profiles for {p}")

    # return g


# class ProfileDetails:
#     def __init__(self, instance_uri, instance_classes: list, general_class):
#         self.available_profiles_dict = {}
#
#         # get general profiles
#         (
#             self.preferred_classes_and_profiles,
#             self.profiles_dict,
#             self.profiles_formats,
#         ) = get_general_profiles(general_class)
#
#         # get profiles specific to the given class, and the default profile
#         (
#             self.available_profiles,
#             self.default_profile,
#         ) = get_class_based_and_default_profiles(
#             instance_uri, self.preferred_classes_and_profiles
#         )
#
#         # slice the total set of profiles by those available for the given class
#         self.available_profiles_dict = {
#             k: v
#             for k, v in self.profiles_dict.items()
#             if k in tuple([i[1] for i in self.available_profiles]) + tuple(["alt"])
#         }
#
#         self.most_specific_class = None
#         # find the most specific class for the feature
#         for klass, _, distance in reversed(self.preferred_classes_and_profiles):
#             if klass in instance_classes:
#                 self.most_specific_class = klass
#                 break
#         if self.most_specific_class is None:
#             self.most_specific_class = OWL.Class


@lru_cache(maxsize=128)
def get_profiles_and_mediatypes(
    classes: List[URIRef],
    requested_profile: URIRef = None,
    requested_mediatype: URIRef = None,
):
    query = select_profile_mediatype(classes, requested_profile, requested_mediatype)
    response = profiles_graph_cache.query(query)
    if len(response.bindings[0]) == 0:
        raise ValueError(
            f"No profiles and or mediatypes could be found to render the resource. The resource class(es) searched for "
            f"were: {', '.join(klass for klass in classes)}"
        )
    top_result = response.bindings[0]
    profile, mediatype, selected_class = (
        top_result["profile"],
        top_result["format"],
        top_result["class"],
    )
    profile_headers = generate_profiles_headers(
        selected_class, response, profile, mediatype
    )
    return profile, mediatype, selected_class, profile_headers


def generate_profiles_headers(selected_class, response, profile, mediatype):
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    if str(mediatype) == "text/html":
        headers["Content-Type"] = "text/turtle"
        # TODO does something else need to be returned? the front end knows what it requested - if HTML was requested,
        #  and RDF is returned, it will know to render it as HTML
    else:
        headers["Content-Type"] = mediatype
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
rel="{"self" if i["def_profile"] and i["def_format"] else "alternate"}"; type="{i["format"]}"; profile="{i["profile"]}"\
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
    return headers
