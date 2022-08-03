import logging
from pathlib import Path
from typing import Optional, Union

from functools import lru_cache

from async_lru import alru_cache
from rdflib import Graph, DCTERMS, SKOS, URIRef, Literal, BNode, SH
from rdflib.namespace import RDF, PROF, Namespace, RDFS, OWL
from connegp import Profile

from prez.config import ENABLED_PREZS, GEO
from prez.services.sparql_utils import (
    sparql_construct,
    sparql_construct_non_async,
    sparql_query,
    sparql_query_multiple,
    sparql_query_multiple_non_async,
)


@lru_cache(maxsize=20)
def create_profiles_graph() -> Graph:
    profiles_g = Graph()
    for f in Path(__file__).parent.glob("*.ttl"):
        profiles_g.parse(f)
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
            profiles_g += r[1]
            logging.info(f"Also using remote profiles for {p}")

    return profiles_g


class ProfileDetails:
    def __init__(self, instance_uri, instance_classes: list, general_class):
        self.available_profiles_dict = {}

        # get general profiles
        (
            self.profiles_g,
            self.preferred_classes_and_profiles,
            self.profiles_dict,
            self.profiles_formats,
        ) = get_general_profiles(general_class)

        # get profiles specific to the given class, and the default profile
        (
            self.available_profiles,
            self.default_profile,
        ) = get_class_based_and_default_profiles(
            instance_uri, self.preferred_classes_and_profiles
        )

        # slice the total set of profiles by those available for the given class
        self.available_profiles_dict = {
            k: v
            for k, v in self.profiles_dict.items()
            if k in tuple([i[1] for i in self.available_profiles]) + tuple(["alt"])
        }

        self.most_specific_class = None
        # find the most specific class for the feature
        for klass, _, distance in reversed(self.preferred_classes_and_profiles):
            if klass in instance_classes:
                self.most_specific_class = klass
                break
        if self.most_specific_class is None:
            self.most_specific_class = OWL.Class


@lru_cache(maxsize=20)
def get_general_profiles(general_class):
    """
    Combines
    1. profiles defined in data (in the triplestore), and
    2. 'standard' profiles defined in Prez
    SPARQL queries these profiles to determine:
    1. What is the preferred profile for a class
    2. Which mediatypes are are available for that profile
    This is run at API startup
    """

    get_class_hierarchy = f"""
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>

        SELECT ?class (count(?mid) as ?distance) ?profile_id ?profile
        WHERE {{
            ?class rdfs:subClassOf* ?mid .
            ?mid rdfs:subClassOf* <{general_class}> .
            ?profile altr-ext:constrainsClass ?class ;
                dcterms:identifier ?profile_id .
        }}
        GROUP BY ?class ?profile_id
        ORDER BY DESC(?distance)
        """
    profiles_formats = {}
    preferred_classes_and_profiles = []

    # ordered list of feature classes and associated preferred profiles
    profiles_g = create_profiles_graph()

    # check for hardcoded API default profiles
    ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
    default_profile_nodeshapes = profiles_g.objects(
        subject=URIRef("http://surroundaustralia.com/profile/prez"),
        predicate=ALTREXT.hasNodeShape,
    )
    class_default_profiles = []

    for nodeshape_bn in default_profile_nodeshapes:
        classes_with_default = profiles_g.value(
            subject=nodeshape_bn, predicate=SH.targetClass
        )
        default_for_class = profiles_g.value(
            subject=nodeshape_bn, predicate=ALTREXT.hasDefaultProfile
        )
        class_default_profiles.append(tuple([classes_with_default, default_for_class]))

    for r in profiles_g.query(get_class_hierarchy):
        distance = str(r["distance"])
        if tuple([r["class"], r["profile"]]) in class_default_profiles:
            distance = 1.5  # this will ensure the profile is selected by default
        preferred_classes_and_profiles.append(
            (str(r["class"]), str(r["profile_id"]), distance)
        )

    # sort by preference order
    preferred_classes_and_profiles.sort(key=lambda x: float(x[2]))

    ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
    for s in profiles_g.subjects(RDF.type, PROF.Profile):
        profile_id = str(profiles_g.value(s, DCTERMS.identifier))
        default_format = str(
            profiles_g.value(subject=s, predicate=ALTREXT.hasDefaultResourceFormat)
        )
        profiles_formats[profile_id] = [default_format]
        other_formats = list(
            set(
                [
                    str(fmt)
                    for fmt in profiles_g.objects(
                        subject=s, predicate=ALTREXT.hasResourceFormat
                    )
                ]
            )
            - set([default_format])
        )
        profiles_formats[profile_id].extend(other_formats)

    # Create ConnegP profile classes and add these to a dictionary
    profiles_dict = {}
    for profile, formats in profiles_formats.items():
        profile_uri = profiles_g.value(
            predicate=DCTERMS.identifier, object=Literal(profile)
        )
        description = profiles_g.value(profile_uri, DCTERMS.description)
        if not description:
            description = profiles_g.value(profile_uri, SKOS.definition)
        label = profiles_g.value(profile_uri, RDFS.label)
        if not label:
            label = profiles_g.value(profile_uri, DCTERMS.title)
            if not label:
                label = profiles_g.value(profile_uri, SKOS.prefLabel)
        profile_id = str(profiles_g.value(profile_uri, DCTERMS.identifier))
        profiles_dict[profile_id] = Profile(
            uri=profile_uri,
            id=profile_id,
            label=label,
            comment=description,
            mediatypes=formats,
            default_mediatype=formats[0],
            languages=["en"],
            default_language="en",
        )

    return (
        profiles_g,
        tuple(preferred_classes_and_profiles),
        profiles_dict,
        profiles_formats,
    )


@lru_cache(maxsize=20)
def get_class_based_and_default_profiles(instance_uri, preferred_classes_and_profiles):
    # retrieve the classes
    r = sparql_query_multiple_non_async(
        f"""SELECT ?class {{ <{instance_uri}> a ?class }}"""
    )
    objects_classes = []
    if r[0] and not r[1]:
        for result in r[0]:
            objects_classes.append(result["class"]["value"])
    else:
        # check for Prez API configured default profiles
        default_profile = preferred_classes_and_profiles[-1][1]
        return preferred_classes_and_profiles, default_profile

    # the available profiles are returned in reverse preference order
    available_profiles = []
    for i, pc in enumerate(preferred_classes_and_profiles):
        for oc in objects_classes:
            if oc == pc[0]:
                available_profiles.append(pc)
    # set the default profile
    default_profile = available_profiles[-1][1]
    return tuple(available_profiles), default_profile


def apply_profile(complete_feature_g: Graph, feature_shapes_g: Graph):
    """
    Apply the profile to the feature graph - returning only the relevant features
    """
    allowed_predicates = [
        so[1]
        for so in feature_shapes_g.subject_objects(
            URIRef("http://www.w3.org/ns/shacl#path")
        )
    ]
    allowed_predicates.extend(
        [RDF.type, DCTERMS.identifier, RDFS.label, RDFS.member, DCTERMS.title]
    )
    triples = [(s, p, o) for s, p, o in complete_feature_g if p in allowed_predicates]
    new_g = Graph()
    for triple in triples:
        new_g.add(triple)
    new_g.namespaces = complete_feature_g.namespaces
    return new_g


async def build_alt_graph(object_of_interest, profiles_formats, available_profiles):
    # build AltRep data
    ALTR = Namespace("http://www.w3.org/ns/dx/conneg/altr#")
    alt_rep = Graph()
    alt_rep.bind("altr", ALTR)
    alt_rep.add((object_of_interest, RDF.type, RDFS.Resource))
    alt_rep.add((object_of_interest, RDFS.label, Literal("placeholder")))

    for available_profile in available_profiles.values():
        for i, fmt in enumerate(profiles_formats[available_profile.id]):
            bn = BNode()
            if i == 0:
                alt_rep.add((bn, RDF.type, ALTR.Representation))
                alt_rep.add((bn, DCTERMS.conformsTo, URIRef(available_profile.uri)))
                alt_rep.add((bn, DCTERMS.format, Literal(fmt)))
                alt_rep.add((object_of_interest, ALTR.hasDefaultRepresentation, bn))

            alt_rep.add((bn, RDF.type, ALTR.Representation))
            alt_rep.add((bn, DCTERMS.conformsTo, URIRef(available_profile.uri)))
            alt_rep.add((bn, DCTERMS.format, Literal(fmt)))
            alt_rep.add((object_of_interest, ALTR.hasRepresentation, bn))

    return alt_rep


@lru_cache(maxsize=20)
def retrieve_relevant_shapes(profile_g, profile, most_specific_class):
    query = f"""PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>
                PREFIX sh: <http://www.w3.org/ns/shacl#>
                PREFIX dash: <http://datashapes.org/dash#>
                CONSTRUCT {{ ?nodeshape_bn sh:property ?pbn ;
                                sh:closed ?closed_profile .
                            ?pbn sh:path ?predicate ;
                                sh:order ?order ;
                                sh:group ?group ;
                                dash:hidden ?hidden . }}
                WHERE {{ <{profile}> altr-ext:hasNodeShape ?nodeshape_bn .
                            ?nodeshape_bn sh:targetClass <{most_specific_class}> ;
                                sh:closed ?closed_profile ;
                                sh:property ?pbn .
                            ?pbn sh:path ?predicate ;
                                sh:order ?order ;
                                sh:group ?group .
                            OPTIONAL {{ ?pbn dash:hidden ?hidden }}
                                }}"""
    results = profile_g.query(query).graph
    return results
