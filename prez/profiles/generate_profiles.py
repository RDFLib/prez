import logging

from aiocache import cached, Cache
from connegp import Profile
from rdflib import Graph, DCTERMS, SKOS, URIRef, Literal, BNode
from rdflib.namespace import RDF, PROF, Namespace, RDFS

from services.sparql_utils import (
    remote_profiles_query,
    sparql_construct,
    sparql_query,
)


@cached(cache=Cache.MEMORY)
async def create_profiles_graph():
    local_profiles_g = Graph().parse(
        "prez/profiles/spaceprez_default_profiles.ttl", format="turtle"
    )
    r = await sparql_construct(remote_profiles_query, "SpacePrez")
    if r[0]:
        remote_profiles_g = r[1]
        profiles_g = local_profiles_g + remote_profiles_g
        logging.info("Using local and remote profiles")
    else:
        profiles_g = local_profiles_g
        logging.info("Using local profiles ONLY - no remote profiles found")
    return profiles_g


@cached(cache=Cache.MEMORY)
async def get_all_profiles():
    """
    Combines
    1. profiles defined in data (in the triplestore), and
    2. 'standard' profiles defined in Prez
    SPARQL queries these profiles to determine:
    1. What is the preferred profile for a class
    2. Which mediatypes are are available for that profile
    This is run at API startup
    """

    get_feature_hierarchy = """
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>

        SELECT ?class (count(?mid) as ?distance) ?profile
        WHERE {
            ?mid rdfs:subClassOf* geo:Feature .
            ?class rdfs:subClassOf* ?mid .

            ?profile altr-ext:constrainsClass ?class .
        }
        GROUP BY ?class
        ORDER BY DESC(?distance)
        """
    profiles_formats = {}
    preferred_classes_and_profiles = []

    # ordered list of feature classes and associated preferred profiles
    profiles_g = await create_profiles_graph()
    for r in profiles_g.query(get_feature_hierarchy):
        preferred_classes_and_profiles.append((str(r["class"]), str(r["profile"])))

    ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
    for s in profiles_g.subjects(RDF.type, PROF.Profile):
        profiles_formats[str(s)] = []
        for p, o in profiles_g.predicate_objects(s):
            # if p == EX.hasAvailableFormat:
            if p == ALTREXT.hasResourceFormat:
                profiles_formats[str(s)].append(str(o))
            # elif p == EX.hasDefaultAvailableFormat:
            elif p == ALTREXT.hasDefaultResourceFormat:
                default_format = str(o)

        profiles_formats[str(s)].remove(default_format)
        profiles_formats[str(s)].insert(0, default_format)

    profiles_dict = {}
    for profile, formats in profiles_formats.items():
        description = profiles_g.value(URIRef(profile), DCTERMS.description)
        if not description:
            description = profiles_g.value(URIRef(profile), SKOS.definition)
        label = profiles_g.value(URIRef(profile), RDFS.label)
        if not label:
            label = profiles_g.value(URIRef(profile), DCTERMS.title)
            if not label:
                label = profiles_g.value(URIRef(profile), SKOS.prefLabel)
        profiles_dict[profile] = Profile(
            uri=profile,
            id=profiles_g.value(URIRef(profile), DCTERMS.identifier),
            label=label,
            comment=description,
            mediatypes=formats,
            default_mediatype=formats[0],
            languages=["en"],
            default_language="en",
        )
    return profiles_g, preferred_classes_and_profiles, profiles_dict, profiles_formats


@cached(cache=Cache.MEMORY, ttl=3600)
async def get_available_profiles(
    feature_uri,
    preferred_classes_and_profiles,
):
    # retrieve the classes
    r = await sparql_query(
        f"""PREFIX dcterms: <{DCTERMS}>
    SELECT ?class {{ <{feature_uri}> a ?class }}""",
        "SpacePrez",
    )
    if r[0]:
        objects_classes = [i["class"]["value"] for i in r[1]]

    # the available profiles are returned in reverse preference order
    available_profiles = []
    for i, pc in enumerate(preferred_classes_and_profiles):
        for oc in objects_classes:
            if oc == pc[0]:
                available_profiles.append(pc[1])
    return available_profiles


@cached(cache=Cache.MEMORY, ttl=3600)
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


@cached(cache=Cache.MEMORY)
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
