import logging

from pathlib import Path
from async_lru import alru_cache
from connegp import Profile
from rdflib import Graph, DCTERMS, SKOS, URIRef, Literal, BNode
from rdflib.namespace import RDF, PROF, Namespace, RDFS

from prez.services.sparql_utils import (
    sparql_construct,
    sparql_query,
)


@alru_cache(maxsize=20)
async def create_profiles_graph():
    profiles_g = Graph()
    for f in Path(__file__).parent.glob("*.ttl"):
        profiles_g.parse(f)
    logging.info("Using local profiles")

    remote_profiles_query = """
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>

        DESCRIBE ?profile ?class 
        WHERE {
          ?profile a prof:Profile .

          OPTIONAL {
            ?class rdfs:subClassOf geo:Feature .
          }
          OPTIONAL {
            ?class rdfs:subClassOf skos:Concept .
          }
        }
        """

    r = await sparql_construct(remote_profiles_query, "VocPrez")
    if r[0]:
        profiles_g += r[1]
        logging.info("Also using remote profiles for VocPrez")

    r = await sparql_construct(remote_profiles_query, "SpacePrez")
    if r[0]:
        profiles_g += r[1]
        logging.info("Also using remote profiles for SpacePrez")

    return profiles_g


class ProfileDetails:
    def __init__(self, general_class, item_uri):
        self.general_class = general_class
        self.item_uri = item_uri
        self.profiles_g = Graph()
        self.preferred_classes_and_profiles = {}
        self.profiles_dict = {}
        self.profiles_formats = {}
        self.available_profiles = []
        self.default_profile = None

    async def get_all_profiles(self):
        (
            profiles_g,
            preferred_classes_and_profiles,
            profiles_dict,
            profiles_formats,
        ) = await get_general_profiles(self.general_class)
        available_profiles, default_profile = await get_specific_profiles(
            self.item_uri, preferred_classes_and_profiles
        )
        self.profiles_g = profiles_g
        self.preferred_classes_and_profiles = preferred_classes_and_profiles
        self.profiles_dict = profiles_dict
        self.profiles_formats = profiles_formats
        self.available_profiles = available_profiles
        self.default_profile = default_profile


@alru_cache(maxsize=20)
async def get_general_profiles(general_class):
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

        SELECT ?class (count(?mid) as ?distance) ?profile_id
        WHERE {{
            ?class rdfs:subClassOf* ?mid .
            ?mid rdfs:subClassOf* <{general_class}> .
            ?profile altr-ext:constrainsClass ?class ;
                dcterms:identifier ?profile_id .
        }}
        GROUP BY ?class
        ORDER BY DESC(?distance)
        """
    profiles_formats = {}
    preferred_classes_and_profiles = []

    # ordered list of feature classes and associated preferred profiles
    profiles_g = await create_profiles_graph()
    for r in profiles_g.query(get_class_hierarchy):
        preferred_classes_and_profiles.append((str(r["class"]), str(r["profile_id"])))

    ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
    for s in profiles_g.subjects(RDF.type, PROF.Profile):
        profile_id = str(profiles_g.value(s, DCTERMS.identifier))
        profiles_formats[profile_id] = []
        for p, o in profiles_g.predicate_objects(s):
            # if p == EX.hasAvailableFormat:
            if p == ALTREXT.hasResourceFormat:
                profiles_formats[profile_id].append(str(o))
            # elif p == EX.hasDefaultAvailableFormat:
            elif p == ALTREXT.hasDefaultResourceFormat:
                default_format = str(o)

        profiles_formats[profile_id].remove(default_format)
        profiles_formats[profile_id].insert(0, default_format)

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


@alru_cache(maxsize=20)
async def get_specific_profiles(
    item_uri,
    preferred_classes_and_profiles,
):
    # retrieve the classes
    r = await sparql_query(
        f"""PREFIX dcterms: <{DCTERMS}>
    SELECT ?class {{ <{item_uri}> a ?class }}""",
        "SpacePrez",
    )
    if r[0] and r[1]:
        objects_classes = [i["class"]["value"] for i in r[1]]
    else:
        default_profile = preferred_classes_and_profiles[0][1]
        return tuple([default_profile]), default_profile

    # the available profiles are returned in reverse preference order
    available_profiles = []
    for i, pc in enumerate(preferred_classes_and_profiles):
        for oc in objects_classes:
            if oc == pc[0]:
                available_profiles.append(pc[1])
    # set the default profile
    default_profile = available_profiles[-1]
    return tuple(available_profiles), default_profile


async def build_alt_graph(object_of_interest, profiles_formats, available_profiles):
    # build AltRep data
    ALTR = Namespace("http://www.w3.org/ns/dx/conneg/altr#")
    alt_rep = Graph()
    alt_rep.bind("altr", ALTR)
    alt_rep.add((object_of_interest, RDF.type, RDFS.Resource))
    alt_rep.add((object_of_interest, RDFS.label, Literal("placeholder")))

    for available_profile in available_profiles:
        for i, fmt in enumerate(profiles_formats[available_profile]):
            bn = BNode()
            if i == 0:
                alt_rep.add((bn, RDF.type, ALTR.Representation))
                alt_rep.add((bn, DCTERMS.conformsTo, URIRef(available_profile)))
                alt_rep.add((bn, DCTERMS.format, Literal(fmt)))
                alt_rep.add((object_of_interest, ALTR.hasDefaultRepresentation, bn))

            alt_rep.add((bn, RDF.type, ALTR.Representation))
            alt_rep.add((bn, DCTERMS.conformsTo, URIRef(available_profile)))
            alt_rep.add((bn, DCTERMS.format, Literal(fmt)))
            alt_rep.add((object_of_interest, ALTR.hasRepresentation, bn))

    return alt_rep


@alru_cache(maxsize=20)
async def filter_results_using_profile(profile_g, profile, most_specific_class):
    query = f"""PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>
                PREFIX sh: <http://www.w3.org/ns/shacl#>
                CONSTRUCT {{ ?pbn sh:path ?predicate ;
                                sh:order ?order ;
                                sh:group ?group . }}
                WHERE {{ <{profile}> altr-ext:hasNodeShape ?nodeshape_bn .
                            ?nodeshape_bn sh:targetClass <{most_specific_class}> ;
                                sh:closed true ;
                                sh:property ?pbn .
                            ?pbn sh:path ?predicate ;
                                sh:order ?order ;
                                sh:group ?group .
                                }}"""
    results = profile_g.query(query).graph
    return results
