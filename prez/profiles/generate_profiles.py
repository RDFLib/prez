import os
import urllib

from aiocache.serializers import PickleSerializer

from services.sparql_utils import remote_profiles_query, sparql_construct
from connegp import Profile
from rdflib import Graph, DCTERMS, SKOS, URIRef, Literal, BNode
from rdflib.namespace import RDF, PROF, Namespace, RDFS
from aiocache import cached, Cache
from functools import lru_cache

# @cached(cache=Cache.MEMORY, key="profiles_g", serializer=PickleSerializer())
@lru_cache()
async def create_profiles_graph():
    # remote_g = Graph("SPARQLStore")
    # remote_g.open(os.getenv("SPACEPREZ_SPARQL_ENDPOINT"))
    r = await sparql_construct(remote_profiles_query, "SpacePrez")
    if r[0]:
        remote_profiles_g = r[1]
    local_profiles_g = Graph().parse(
        "prez/profiles/spaceprez_default_profiles.ttl", format="turtle"
    )
    profiles_g = local_profiles_g + remote_profiles_g
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
    # TODO check what happens in case of class having two profiles - probably both get appended
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


async def get_available_profiles(
    objects_classes,
    preferred_classes_and_profiles,
):
    "the available profiles are returned in reverse preference order"
    available_profiles = []
    for i, pc in enumerate(preferred_classes_and_profiles):
        for oc in objects_classes:
            if oc == pc[0]:
                available_profiles.append(pc[1])
    return available_profiles


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


# @cached(cache=Cache.MEMORY, key="profile", serializer=PickleSerializer())
async def get_predicate_filters(g, profile):
    # get the predicate filter addresses
    ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
    pred_lists = []
    bn = g.value(subject=URIRef(profile), predicate=ALTREXT.hasPredicateFilters)
    if bn:

        def inner_func(bn):
            first = g.value(subject=bn, predicate=RDF.first)
            rest = g.value(subject=bn, predicate=RDF.rest)
            return first, rest

        while bn != RDF.nil:
            first, bn = inner_func(bn)
            pred_lists.append(first)

    # add the predicate filters to a list
    pred_query_values = []
    for i, plist in enumerate(pred_lists):
        preds = urllib.request.urlopen(plist)
        pred_query_values.append(
            f"VALUES ?p{i+1}"
            + "{"
            + " ".join([f"<{pred.decode()}>" for pred in preds]).replace("\n", "")
            + "}"
        )
    return pred_query_values
