import logging
from functools import lru_cache
from typing import List, Optional, Tuple, Union

from rdflib import Graph, URIRef, RDFS, DCTERMS, Namespace

from prez.cache import tbox_cache, profiles_graph_cache
from prez.models import (
    CatalogItem,
    CatalogMembers,
    SpatialItem,
    SpatialMembers,
    VocabItem,
    VocabMembers,
)

log = logging.getLogger(__name__)

ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
PREZ = Namespace("https://prez.dev/")


def generate_insert_context(settings, prez: str):
    """ """
    topmost_classes = settings.top_level_classes[prez]
    collection_classes = settings.collection_classes[prez]
    member_relation = {
        "SpacePrez": "rdfs:member",
        "VocPrez": "^skos:inScheme",
        "CatPrez": "dcterms:hasPart",
    }
    topmost_class_collection = {
        "SpacePrez": "prez:DatasetList",
        "VocPrez": "prez:VocabCollection",
        "CatPrez": "prez:CatalogList",
    }
    insert = f"""PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
INSERT {{
    GRAPH prez:{prez.lower()}-system-graph {{?support_graph_uri prez:hasContextFor ?instance_of_main_class .
     {topmost_class_collection[prez]} rdfs:member ?instance_of_top_class . }}
	GRAPH ?support_graph_uri {{ ?instance_of_main_class dcterms:identifier ?prez_id .
    	?member dcterms:identifier ?prez_mem_id . }}
}}
WHERE {{
  {{
    ?instance_of_main_class a ?collection_class .
        VALUES ?collection_class {{ {(chr(10) + 2 * chr(9)).join('<' + str(uri) + '>' for uri in collection_classes)} }}
    OPTIONAL {{?instance_of_top_class a ?topmost_class
        VALUES ?topmost_class {{ {(chr(10) + 2 * chr(9)).join('<' + str(uri) + '>' for uri in topmost_classes)} }}
    }}
    MINUS {{ GRAPH prez:{prez.lower()}-system-graph {{?a_context_graph prez:hasContextFor ?instance_of_main_class}}
    }}
    OPTIONAL {{?instance_of_main_class dcterms:identifier ?id
        BIND(DATATYPE(?id) AS ?dtype_id)
        FILTER(?dtype_id = xsd:token)
        }}
    OPTIONAL {{?instance_of_main_class {member_relation[prez]} ?member
        OPTIONAL {{?member dcterms:identifier ?mem_id
            BIND(DATATYPE(?mem_id) AS ?dtype_mem_id)
            FILTER(?dtype_mem_id = xsd:token) }} }}
    }}
    BIND(STRDT(COALESCE(?id,MD5(STR(?instance_of_main_class))), prez:slug) AS ?prez_id)
    BIND(STRDT(COALESCE(?mem_id,MD5(STR(?member))), prez:slug) AS ?prez_mem_id)
    BIND(URI(CONCAT(STR(?instance_of_main_class),"#support-graph")) AS ?support_graph_uri)
}}"""
    return insert


# def generate_listing_construct_from_general_class(
#         parent_item,
#         profile,
#         page: Optional[int] = 1,
#         per_page: Optional[int] = 20,
#         ):
#     """
#     For a given general class, find instances of this class.
#     Generates a SPARQL construct query for a listing of items
#     """
#     construct_query = f"""PREFIX dcterms: <http://purl.org/dc/terms/>
# PREFIX prez: <https://prez.dev/>
# PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
# PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
# PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
# PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
#
# CONSTRUCT {{
# <{parent_item.uri}> rdfs:member ?item .'
# ?item a <{parent_item.general_class}> ;
#     dcterms:identifier ?id }}
# WHERE {{
# <{parent_item.uri}> rdfs:member ?item .'
# ?item a <{parent_item.general_class}> ;
#     dcterms:identifier ?id }}
#
#     }} {f"LIMIT {per_page} OFFSET {(page - 1) * per_page}" if page is not None and per_page is not None else ""}
#     """
#     return construct_query


def generate_listing_construct_from_uri(
    parent_item,
    profile,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
):
    """
    For a given URI, finds items with the specified relation(s).
    Generates a SPARQL construct query for a listing of items, including labels
    """
    (
        inbound_children,
        inbound_parents,
        outbound_children,
        outbound_parents,
    ) = get_listing_predicates(profile, parent_item.selected_class)
    if (
        parent_item.uri
        and not inbound_children
        and not inbound_parents
        and not outbound_children
        and not outbound_parents
    ):
        log.warning(
            f"Requested listing of objects related to {parent_item.uri}, however the profile {profile} does not"
            f" define any listing relations for this for this class, for example outbound children."
        )
        return ""
    construct_query = f"""PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

CONSTRUCT {{
    {f'<{parent_item.uri}> ?outbound_children ?item .{chr(10)}'
     f'?item prez:link ?outbound_children_link .{chr(10)}' if outbound_children else ""}\
    {f'<{parent_item.uri}> ?outbound_parents ?item .{chr(10)}'
     f'?item prez:link ?outbound_parents_link .{chr(10)}' if outbound_parents else ""}\
    {f'?inbound_child_s ?inbound_child <{parent_item.uri}> ;{chr(10)}'
     f'prez:link ?inbound_children_link .{chr(10)}' if inbound_children else ""}\
    {f'?inbound_parent_s ?inbound_parent <{parent_item.uri}> ;{chr(10)}'
     f'prez:link ?inbound_parent_link .{chr(10)}' if inbound_parents else ""}\
    ?item rdfs:label ?label .
    {f'''prez:memberList a rdf:Bag ;
                rdfs:member ?item .
    ?item prez:link ?outbound_general_link''' if not parent_item.uri else ""} \
    }}
WHERE {{
{generate_outbound_predicates(parent_item, outbound_children, outbound_parents)} \
{generate_inbound_predicates(parent_item, inbound_children, inbound_parents)} \
    ?item rdfs:label|dcterms:title|skos:prefLabel ?label .
{generate_id_listing_binds(parent_item, inbound_children, inbound_parents, outbound_children, outbound_parents)}
    }} {f"LIMIT {per_page} OFFSET {(page - 1) * per_page}" if page is not None and per_page is not None else ""}
    """
    return construct_query


@lru_cache(maxsize=128)
def generate_item_construct(item, profile: URIRef):
    object_uri = item.uri
    (
        include_predicates,
        exclude_predicates,
        inverse_predicates,
        sequence_predicates,
    ) = get_item_predicates(profile, item.selected_class)
    bnode_depth = profiles_graph_cache.value(
        profile,
        ALTREXT.hasBNodeDepth,
        None,
        default=2,
    )
    construct_query = f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n
CONSTRUCT {{
\t<{object_uri}> ?p ?o1 .
{generate_sequence_construct(object_uri, sequence_predicates) if sequence_predicates else ""}
{f'{chr(9)}?s ?inbound_p <{object_uri}> .' if inverse_predicates else ""}
{generate_bnode_construct(bnode_depth)} \
\n}}
WHERE {{
    {{
    <{object_uri}> ?p ?o1 . {chr(10)} \
{generate_sequence_construct(object_uri, sequence_predicates) if sequence_predicates else chr(10)} \
    {f'?s ?inbound_p <{object_uri}>{chr(10)}' if inverse_predicates else chr(10)} \
    {generate_include_predicates(include_predicates)} \
    {generate_inverse_predicates(inverse_predicates)} \
    {generate_bnode_select(bnode_depth)} \
    }} \
}}
"""
    return construct_query


def generate_outbound_predicates(item, outbound_children, outbound_parents):
    where = ""
    if item.uri:
        if outbound_children:
            where += f"""<{item.uri}> ?outbound_children ?item .
            ?item dcterms:identifier ?outbound_children_id .
            FILTER(DATATYPE(?outbound_children_id) = prez:slug)
            VALUES ?outbound_children {{ {" ".join('<' + str(pred) + '>' for pred in outbound_children)} }}\n"""
        if outbound_parents:
            where += f"""<{item.uri}> ?outbound_parents ?item .
            ?item dcterms:identifier ?outbound_parents_id .
            FILTER(DATATYPE(?outbound_parents_id) = prez:slug)
            VALUES ?outbound_parents {{ {" ".join('<' + str(pred) + '>' for pred in outbound_parents)} }}\n"""
        if not outbound_children and not outbound_parents:
            where += "VALUES ?outbound_children {}\nVALUES ?outbound_parents {}"
        return where
    return ""


def generate_inbound_predicates(item, inbound_children, inbound_parents):
    if not inbound_children and not inbound_parents:
        return ""
    where = ""
    if inbound_children:
        where += f"""?inbound_child_s ?inbound_child <{item.uri}> ;
        dcterms:identifier ?inbound_children_id .
        FILTER(DATATYPE(?inbound_children_id) = prez:slug)
        VALUES ?inbound_child {{ {" ".join('<' + str(pred) + '>' for pred in inbound_children)} }}\n"""
    if inbound_parents:
        where += f"""?inbound_parent_s ?inbound_parent <{item.uri}> ;
        dcterms:identifier ?inbound_parent_id .
        FILTER(DATATYPE(?inbound_parent_id) = prez:slug)
        VALUES ?inbound_parent {{ {" ".join('<' + str(pred) + '>' for pred in inbound_parents)} }}\n"""
    # if not inbound_children and not inbound_parents:
    #     where += "VALUES ?inbound_child {}\nVALUES ?inbound_parent {}"
    return where


def generate_id_listing_binds(item, ic, ip, oc, op):
    """
    Generate the BIND statements for the inbound and outbound predicates
    """
    binds = ""
    if ic:
        binds += f"""BIND(CONCAT("{item.link_constructor}", "/", STR(?inbound_children_id))\
AS ?inbound_children_link)\n"""
    if oc:
        binds += f"""BIND(CONCAT("{item.link_constructor}", "/", STR(?outbound_children_id))\
AS ?outbound_children_link)\n"""
    if ip:
        binds += f"""BIND("{item.link_constructor}" AS ?inbound_parent_link)\n"""
    if op:
        binds += f"""BIND("{item.link_constructor}" AS ?outbound_parent_link)\n"""
    if not binds:  # for general listings of objects
        binds += f"""BIND(CONCAT("{item.link_constructor}", "/", STR(?outbound_id))\
AS ?outbound_general_link)\n"""
    return binds


def generate_include_predicates(include_predicates):
    """
    Generates a SPARQL VALUES clause for a list of predicates, of the form:
    VALUES ?p { <http://example1.com> <http://example2.com> }
    """
    if include_predicates:
        return f"""VALUES ?p{{\n{chr(10).join([f"<{p}>" for p in include_predicates])}\n}}"""
    return ""


def generate_inverse_predicates(inverse_predicates):
    """
    Generates a SPARQL VALUES clause for a list of inverse predicates, of the form:
    VALUES ?inbound_p { <http://example1.com> <http://example2.com> }
    """
    if inverse_predicates:
        return f"""VALUES ?inbound_p{{\n{chr(10).join([f"<{p}>" for p in inverse_predicates])}\n}}"""
    return ""


def generate_sequence_construct(object_uri, sequence_predicates):
    """
    Generates part of a SPARQL CONSTRUCT query for property paths, given a list of lists of property paths.
    """
    if sequence_predicates:
        all_sequence_construct = ""
        for predicate_list in sequence_predicates:
            construct_and_where = f"\t<{object_uri}> <{predicate_list[0]}> ?seq_o1 ."
            for i in range(1, len(predicate_list)):
                construct_and_where += (
                    f"\n\t?seq_o{i} <{predicate_list[i]}> ?seq_o{i + 1} ."
                )
            all_sequence_construct += construct_and_where
        return all_sequence_construct
    return ""


def generate_bnode_construct(depth):
    """
    Generate the construct query for the bnodes, this is of the form:
    ?o1 ?p2 ?o2 .
        ?o2 ?p3 ?o3 .
        ...
    """
    return "\n" + "\n".join(
        [f"\t?o{i + 1} ?p{i + 2} ?o{i + 2} ." for i in range(depth)]
    )


def generate_bnode_select(depth):
    """
    Generates a SPARQL select string for bnodes to a given depth, of the form:
    OPTIONAL {
        FILTER(ISBLANK(?o1))
        ?o1 ?p2 ?o2 ;
        OPTIONAL {
            FILTER(ISBLANK(?o2))
            ?o2 ?p3 ?o3 ;
            OPTIONAL { ...
                }
            }
        }
    """
    part_one = "\n".join(
        [
            f"""{chr(9) * (i + 1)}OPTIONAL {{
{chr(9) * (i + 2)}FILTER(ISBLANK(?o{i + 1}))
{chr(9) * (i + 2)}?o{i + 1} ?p{i + 2} ?o{i + 2} ."""
            for i in range(depth)
        ]
    )
    part_two = "".join(
        [f"{chr(10)}{chr(9) * (i + 1)}}}" for i in reversed(range(depth))]
    )
    return part_one + part_two


async def get_annotation_properties(
    item_graph: Graph,
    label_prop: URIRef = RDFS.label,
    description_prop: URIRef = DCTERMS.description,
    explanation_prop: URIRef = DCTERMS.provenance,
):
    """
    Gets annotation data used for HTML display.
    This includes the label, description, and provenance, if available.
    """
    terms = set(i for i in item_graph.predicates() if isinstance(i, URIRef)) | set(
        i for i in item_graph.objects() if isinstance(i, URIRef)
    )
    if not terms:
        return None, Graph()
    # read labels from the tbox cache, this should be the majority of labels
    uncached_terms, labels_g = get_annotations_from_tbox_cache(
        terms, label_prop, description_prop, explanation_prop
    )
    queries_for_uncached = f"""CONSTRUCT {{ ?term ?prop ?label }}
        WHERE {{ ?term ?prop ?label .
        VALUES ?term {{ {" ".join('<' + str(term) + '>' for term in uncached_terms)} }}
        VALUES ?prop {{ {" ".join('<' + str(prop) + '>' for prop in [label_prop, description_prop, explanation_prop])} }}
        FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
        }}"""
    # remove any queries we previously didn't get a result for from the SPARQL endpoint
    return queries_for_uncached, labels_g


def get_annotations_from_tbox_cache(
    terms: List[URIRef], label_prop, description_prop, explanation_prop
):
    """
    Gets labels from the TBox cache, returns a list of terms that were not found in the cache, and a graph of labels
    """
    labels_from_cache = Graph()
    terms_list = list(terms)
    labels = list(tbox_cache.triples_choices((terms_list, label_prop, None)))
    descriptions = list(
        tbox_cache.triples_choices((terms_list, description_prop, None))
    )
    provenance = list(tbox_cache.triples_choices((terms_list, explanation_prop, None)))
    all = labels + descriptions + provenance
    for triple in all:
        labels_from_cache.add(triple)
    uncached_terms = list(set(terms) - set(triple[0] for triple in all))
    return uncached_terms, labels_from_cache


# hit the count cache first, if it's not there, hit the SPARQL endpoint
def generate_listing_count_construct(
    item: Union[
        SpatialItem,
        SpatialMembers,
        VocabMembers,
        VocabItem,
        CatalogItem,
        CatalogMembers,
    ]
):
    """
    Generates a SPARQL construct query to count either:
    1. the members of a collection, if a URI is given, or;
    2. the number of instances of a general class, given a general class.
    """
    if item.uri:
        query_implicit = f"""PREFIX prez: <https://prez.dev/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CONSTRUCT {{ <{item.uri}> prez:count ?count }}
WHERE {{
    SELECT (COUNT(?item) as ?count) {{
        <{item.uri}> rdfs:member ?item .
    }}
}}"""
        return query_implicit
    else:  # item.selected_class
        query = f"""PREFIX prez: <https://prez.dev/>

CONSTRUCT {{ <{item.general_class}> prez:count ?count }}
WHERE {{
    SELECT (COUNT(?item) as ?count) {{
        ?item a <{item.general_class}> .
    }}
}}"""
        return query


def get_relevant_shape_bns_for_profile(selected_class, profile):
    """
    Gets the shape blank nodes URIs from the profiles graph for a given profile.
    """
    if not profile:
        return None
    shape_bns = list(
        profiles_graph_cache.objects(
            subject=profile,
            predicate=ALTREXT.hasNodeShape,
        )
    )
    if not shape_bns:
        return None
    relevant_shape_bns = [
        triple[0]
        for triple in profiles_graph_cache.triples_choices(
            (
                list(shape_bns),
                URIRef("http://www.w3.org/ns/shacl#targetClass"),
                selected_class,
            )
        )
    ]
    return relevant_shape_bns


def get_listing_predicates(profile, selected_class):
    """
    Gets predicates relevant to listings of objects as specified in the profile.
    This is used in two scenarios:
    1. "Collection" endpoints, for top level listing of objects of a particular type
    2. For a specific object, where it has members
    The predicates retrieved from profiles are:
    - inbound children, for example where the object of interest is a Concept Scheme, and is linked to Concept(s) via
        the predicate skos:inScheme
    - outbound children, for example where the object of interest is a Feature Collection, and is linked to Feature(s)
        via the predicate rdfs:member
    - inbound parents, for example where the object of interest is a Feature Collection, and is linked to Dataset(s) via
        the predicate dcterms:hasPart
    - outbound parents, for example where the object of interest is a Concept, and is linked to Concept Scheme(s) via
    the predicate skos:inScheme
    """
    shape_bns = get_relevant_shape_bns_for_profile(selected_class, profile)
    if not shape_bns:
        return [], [], [], []
    inbound_children = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.inboundChildren,
                None,
            )
        )
    ]
    inbound_parents = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.inboundParents,
                None,
            )
        )
    ]
    outbound_children = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.outboundChildren,
                None,
            )
        )
    ]
    outbound_parents = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.outboundParents,
                None,
            )
        )
    ]
    return inbound_children, inbound_parents, outbound_children, outbound_parents


def get_item_predicates(profile, selected_class):
    """
    Gets any predicates specified in the profile, this includes:
    - predicates to include. Uses sh:path
    - predicates to exclude. Uses sh:path in conjunction with dash:hidden.
    - inverse path predicates to include (inbound links to the object). Uses sh:inversePath.
    - sequence path predicates to include, expressed as a list. Uses sh:sequencePath.
    """
    shape_bns = get_relevant_shape_bns_for_profile(selected_class, profile)
    if not shape_bns:
        return None, None, None, None
    includes = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (shape_bns, URIRef("http://www.w3.org/ns/shacl#path"), None)
        )
    ]
    excludes = ...
    inverses = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (shape_bns, URIRef("http://www.w3.org/ns/shacl#inversePath"), None)
        )
    ]
    _sequence_nodes = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                URIRef("http://www.w3.org/ns/shacl#sequencePath"),
                None,
            )
        )
    ]
    sequence_paths = [
        [path_item for path_item in profiles_graph_cache.items(i)]
        for i in _sequence_nodes
    ]
    return includes, excludes, inverses, sequence_paths


def select_profile_mediatype(
    classes: List[URIRef],
    requested_profile: URIRef = None,
    requested_mediatypes: List[Tuple] = None,
):
    """
    Returns a SPARQL SELECT query which will determine the profile and mediatype to return based on user requests,
    defaults, and the availability of these in profiles.

    The following logic is used:
    NB: Most specific class refers to the rdfs:Class of an object which has the most specific rdfs:subClassOf links to
    the general class delivered by that API endpoint. The general classes delivered by each API endpoint are:

    1. If a profile and mediatype are requested, they are returned if a matching profile which has the requested
    mediatype is found, otherwise the default profile for the most specific class is returned, with its default
    mediatype.
    2. If a profile only is requested, if it can be found it is returned, otherwise the default profile for the most
    specific class is returned. In both cases the default mediatype is returned.
    3. If a mediatype only is requested, the default profile for the most specific class is returned, and if the
    requested mediatype is available for that profile, it is returned, otherwise the default mediatype for that profile
    is returned.
    4. If neither a profile nor mediatype is requested, the default profile for the most specific class is returned,
    with the default mediatype for that profile.
    """
    query = f"""
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://prez.dev/>

SELECT ?profile ?title ?class (count(?mid) as ?distance) ?req_profile ?def_profile ?format ?req_format ?def_format ?token

WHERE {{
  VALUES ?class {{{" ".join('<' + str(klass) + '>' for klass in classes)}}}
  ?class rdfs:subClassOf* ?mid .
  ?mid rdfs:subClassOf* ?general_class .
  VALUES ?general_class {{ dcat:Dataset geo:FeatureCollection prez:FeatureCollectionList prez:FeatureList geo:Feature
  skos:ConceptScheme skos:Concept skos:Collection prez:DatasetList prez:VocPrezCollectionList prez:SchemesList
  prez:CatalogList dcat:Catalog dcat:Resource }}
  ?profile altr-ext:constrainsClass ?class ;
           altr-ext:hasResourceFormat ?format ;
           dcterms:identifier ?token ;
           dcterms:title ?title .
  {f'BIND(?profile=<{requested_profile}> as ?req_profile)' if requested_profile else ''}
  BIND(EXISTS {{ ?shape sh:targetClass ?class ;
                       altr-ext:hasDefaultProfile ?profile }} AS ?def_profile)
  {generate_mediatype_if_statements(requested_mediatypes) if requested_mediatypes else ''}
  BIND(EXISTS {{ ?profile altr-ext:hasDefaultResourceFormat ?format }} AS ?def_format)
}}

GROUP BY ?class ?profile ?req_profile ?def_profile ?format ?req_format ?def_format
ORDER BY DESC(?req_profile) DESC(?distance) DESC(?def_profile) DESC(?req_format) DESC(?def_format)
        """
    return query


def generate_mediatype_if_statements(requested_mediatypes: list):
    """
    Generates a list of if statements which will be used to determine the mediatype to return based on user requests,
    and the availability of these in profiles.
    These are of the form:
      BIND(
        IF(?format="application/ld+json", "0.9",
          IF(?format="text/html", "0.8",
            IF(?format="image/apng", "0.7", ""))) AS ?req_format)
    """
    # TODO ConnegP appears to return a tuple of q values and profiles for headers, and only profiles (no q values) if they
    # are not specified in QSAs.
    if not isinstance(next(iter(requested_mediatypes)), tuple):
        requested_mediatypes = [(1, mt) for mt in requested_mediatypes]

    line_join = "," + "\n"
    ifs = (
        f"BIND(\n"
        f"""{line_join.join({'IF(?format="' + tup[1] + '", "' + str(tup[0]) + '"' for tup in requested_mediatypes})}"""
        f""", ""{')' * len(requested_mediatypes)}\n"""
        f"AS ?req_format)"
    )
    return ifs


def startup_count_objects():
    """
    Retrieves hardcoded counts for collections in the dataset (feature collections, datasets etc.)
    """
    return f"""PREFIX prez: <https://prez.dev/>
CONSTRUCT {{ ?collection prez:count ?count }}
WHERE {{ ?collection prez:count ?count }}"""


def ask_system_graph(prez_flavour: str):
    """
    Checks if the system graph exists in the triple store.
    """
    return f"ASK {{ GRAPH <{PREZ[prez_flavour.lower() + '-system-graph']}> {{ ?s ?p ?o }} }} LIMIT 1"
