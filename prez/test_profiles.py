# tests profiles/generate_profiles

from pathlib import Path
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import DCAT, DCTERMS, PROF, RDF, RDFS, SKOS
from connegp import Profile


profiles_g = Graph()
for f in Path(Path(__file__).parent / "profiles").glob("*.ttl"):
    profiles_g.parse(f)
    print(len(profiles_g))

general_class = DCAT.Dataset

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

for r in profiles_g.query(get_class_hierarchy):
    preferred_classes_and_profiles.append((str(r["class"]), str(r["profile_id"])))

# print(preferred_classes_and_profiles)

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

# import pprint
# pprint.pprint(profiles_formats)

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

# pprint.pprint(profiles_dict)

# the available profiles are returned in reverse preference order
available_profiles = []
for i, pc in enumerate(preferred_classes_and_profiles):
    for oc in [str(DCAT.Dataset)]:
        if oc == pc[0]:
            available_profiles.append(pc[1])
# set the default profile
default_profile = available_profiles[-1]

print(tuple(available_profiles))
print(default_profile)