from functools import lru_cache
from typing import List, Optional, Tuple

from rdflib import Graph, URIRef, RDFS, DCTERMS

from prez.cache import tbox_cache, profiles_graph_cache


def generate_listing_construct(
    item,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    profile: Optional[str] = None,
):
    """
    Generates a SPARQL construct query for a listing of items, including labels
    """
    _, _, _, _, members_predicates = get_profile_predicates(profile, item.general_class)
    construct_query = f"""PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://kurrawong.net/prez/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>

CONSTRUCT {{ {f'<{item.uri}> ?members_pred ?item .' if item.uri else ""}
            ?item dcterms:identifier ?id ;
                  rdfs:label ?label ;
                  prez:link ?link .
{           f'prez:memberList a rdf:Bag ;'
                            f'?members_pred ?item .' if not item.uri else ""} \
    }}
WHERE {{ \
{generate_members_predicates(item, members_predicates)} \
{chr(10) + chr(9) + f'?item a <{item.general_class}> .' if not item.uri else chr(10)} \
    ?item dcterms:identifier ?id ;
        rdfs:label|dcterms:title|skos:prefLabel ?label .
  	FILTER(DATATYPE(?id) = xsd:token)
  	BIND(CONCAT("{item.link_constructor}", STR(?id)) AS ?link)
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
        _,
    ) = get_profile_predicates(profile, item.general_class)
    bnode_depth = profiles_graph_cache.value(
        profile,
        URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#hasBNodeDepth"),
        None,
        default=2,
    )
    construct_query = f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n
CONSTRUCT {{
\t<{object_uri}> ?p ?o1 .
{generate_sequence_construct(object_uri, sequence_predicates) if sequence_predicates else ""} \
{f'{chr(9)}?s ?inbound_p <{object_uri}> .' if inverse_predicates else ""} \
{generate_bnode_construct(bnode_depth)} \
\n}}
WHERE {{
    {{
    <{object_uri}> ?p ?o1 . \
    {generate_sequence_construct(object_uri, sequence_predicates) if sequence_predicates else chr(10)} \
    {f'?s ?inbound_p <{object_uri}>{chr(10)}' if inverse_predicates else chr(10)} \
    {generate_include_predicates(include_predicates)} \
    {generate_inverse_predicates(inverse_predicates)} \
    {generate_bnode_select(bnode_depth)} \
    }} \
}}
"""
    return construct_query


def generate_members_predicates(item, members_predicates):
    if members_predicates:
        return f"""<{item.uri}> ?members_pred ?item .
    VALUES ?members_pred {{ {" ".join('<'+pred+'>' for pred in members_predicates)} }}"""
    return ""


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
    object_graph: Graph,
    label_property: URIRef = URIRef("http://www.w3.org/2000/01/rdf-schema#label"),
):
    """
    Gets annotation data used for HTML display.
    This includes the label, description, and provenance, if available.
    """
    terms = set(i for i in object_graph.predicates() if isinstance(i, URIRef)) | set(
        i for i in object_graph.objects() if isinstance(i, URIRef)
    )
    if not terms:
        return None, Graph()
    # read labels from the tbox cache, this should be the majority of labels
    uncached_terms, labels_g = get_annotations_from_tbox_cache(terms)
    # read remaining labels from the SPARQL endpoint
    #     queries_for_uncached = [
    #         f"""CONSTRUCT {{ <{term}> <{label_property}> ?label }}
    # WHERE {{ <{term}> <{label_property}> ?label
    # FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
    # }}"""
    #         for term in uncached_terms
    #     ]
    queries_for_uncached = f"""CONSTRUCT {{ ?term <{label_property}> ?label }}
        WHERE {{ ?term <{label_property}> ?label .
        VALUES ?term {{ {" ".join('<' + str(term) + '>' for term in uncached_terms)} }}
        FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
        }}"""
    # remove any queries we previously didn't get a result for from the SPARQL endpoint
    # queries_for_uncached = list(set(queries_for_uncached) - set(missing_annotations))
    # untested assumption is running multiple queries in parallel is faster than running one query for all labels
    return queries_for_uncached, labels_g


def get_annotations_from_tbox_cache(terms: List[URIRef]):
    """
    Gets labels from the TBox cache, returns a list of terms that were not found in the cache, and a graph of labels
    """
    labels_from_cache = Graph()
    terms_list = list(terms)
    labels = list(tbox_cache.triples_choices((terms_list, RDFS.label, None)))
    descriptions = list(
        tbox_cache.triples_choices((terms_list, DCTERMS.description, None))
    )
    provenance = list(
        tbox_cache.triples_choices((terms_list, DCTERMS.provenance, None))
    )
    all = labels + descriptions + provenance
    for triple in all:
        labels_from_cache.add(triple)
    uncached_terms = list(set(terms) - set(triple[0] for triple in all))
    return uncached_terms, labels_from_cache


def generate_listing_count_construct(
    collection_uri: Optional[URIRef] = None, general_class: Optional[URIRef] = None
):
    """
    Generates a SPARQL construct query to count either:
    1. the members of a collection, given a collection URI, or;
    2. the number of instances of a general class, given a general class.
    """
    if not (collection_uri or general_class):
        raise ValueError("Either a collection URI or a general class must be provided")
    if collection_uri:
        query_explicit = f"""PREFIX prez: <https://kurrawong.net/prez/>

CONSTRUCT {{ <{collection_uri}> prez:count ?count }}
WHERE {{ <{collection_uri}> prez:count ?count }}"""

        query_implicit = f"""PREFIX prez: <https://kurrawong.net/prez/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CONSTRUCT {{ <{collection_uri}> prez:count ?count }}
WHERE {{
    SELECT (COUNT(?item) as ?count) {{
        <{collection_uri}> rdfs:member ?item .
    }}
}}"""
        return query_explicit, query_implicit
    else:  # general_class
        return f"""PREFIX prez: <https://kurrawong.net/prez/>

CONSTRUCT {{ <{general_class}> prez:count ?count }}
WHERE {{
    SELECT (COUNT(?item) as ?count) {{
        ?item a <{general_class}> .
    }}
}}"""


def get_profile_predicates(profile, general_class):
    """
    Gets any predicates specified in the profile, this includes:
    - predicates to include. Uses sh:path
    - predicates to exclude. Uses sh:path in conjunction with dash:hidden.
    - inverse path predicates to include (inbound links to the object). Uses sh:inversePath.
    - sequence path predicates to include, expressed as a list. Uses sh:sequencePath.
    - member links to include. Uses altr-ext:members.
    """
    shape_bns = profiles_graph_cache.objects(
        subject=profile,
        predicate=URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#hasNodeShape"),
    )
    relevant_shape_bns = [
        triple[0]
        for triple in profiles_graph_cache.triples_choices(
            (
                list(shape_bns),
                URIRef("http://www.w3.org/ns/shacl#targetClass"),
                general_class,
            )
        )
    ]
    if not relevant_shape_bns:
        return None, None, None, None, None
    includes = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (relevant_shape_bns, URIRef("http://www.w3.org/ns/shacl#path"), None)
        )
    ]
    excludes = ...
    inverses = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (relevant_shape_bns, URIRef("http://www.w3.org/ns/shacl#inversePath"), None)
        )
    ]
    sequence_nodes = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                relevant_shape_bns,
                URIRef("http://www.w3.org/ns/shacl#sequencePath"),
                None,
            )
        )
    ]
    sequence_paths = [
        [path_item for path_item in profiles_graph_cache.items(i)]
        for i in sequence_nodes
    ]
    members = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                relevant_shape_bns,
                URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#members"),
                None,
            )
        )
    ]
    return includes, excludes, inverses, sequence_paths, members


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
PREFIX prez: <https://kurrawong.net/prez/>

SELECT ?profile ?class (count(?mid) as ?distance) ?req_profile ?def_profile ?format ?req_format ?def_format

WHERE {{
  VALUES ?class {{{" ".join('<' + klass + '>' for klass in classes)}}}
  ?class rdfs:subClassOf* ?mid .
  ?mid rdfs:subClassOf* ?general_class .
  VALUES ?general_class {{ dcat:Dataset geo:FeatureCollection prez:FeatureCollectionList prez:FeatureList geo:Feature
  skos:ConceptScheme skos:Concept skos:Collection prez:DatasetList prez:VocPrezCollectionList prez:SchemesList
  prez:CatalogList dcat:Catalog dcat:Resource }}
  ?profile altr-ext:constrainsClass ?class ;
           altr-ext:hasResourceFormat ?format .
  {f'BIND(?profile=<{requested_profile}> as ?req_profile)' if requested_profile else ''}
  BIND(EXISTS {{ ?shape sh:targetClass ?class ;
                       altr-ext:hasDefaultProfile ?profile }} AS ?def_profile)
  {generate_mediatype_if_statements(requested_mediatypes) if requested_mediatypes else ''}
  BIND(EXISTS {{ ?profile altr-ext:hasDefaultResourceFormat ?format }} AS ?def_format)
}}

GROUP BY ?class ?profile ?req_profile ?def_profile ?format ?req_format ?def_format
ORDER BY DESC(?req_profile) DESC(?distance) DESC(?def_profile) DESC(?req_format) DESC(?def_format)
LIMIT 1
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
    line_join = "," + "\n"
    ifs = (
        f"BIND(\n"
        f"""{line_join.join({'IF(?format="' + tup[1] + '", "' + str(tup[0]) + '"' for tup in requested_mediatypes})}"""
        f""", ""{')' * len(requested_mediatypes)}\n"""
        f"AS ?req_format)"
    )
    return ifs


def generage_large_outbound_links(
    uri: URIRef, outbound_predicate: URIRef, limit: int = 10
):
    outbound_pred_subset = f"""UNION
\t{{
\tSELECT * {{
\t<{uri}> <{outbound_predicate[0]}> ?o1 ;
\t\t?p ?o1
\t}} LIMIT {limit}}}
    """
    return outbound_pred_subset
