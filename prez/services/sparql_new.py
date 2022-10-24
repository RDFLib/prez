from typing import List, Optional

from rdflib import Graph, URIRef, RDFS, DCTERMS

from prez.cache import tbox_cache, missing_annotations
from prez.models.spaceprez_item import SpatialItem
from prez.profiles.generate_profiles import create_profiles_graph


def generate_listing_construct(
    item: SpatialItem,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    profile: dict = {},  # unused - we don't currently filter or otherwise change listings based on profiles
):
    """
    Generates a SPARQL construct query for a listing of items, including labels
    """
    construct_query = f"""PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prez: <https://kurrawong.net/prez/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>

CONSTRUCT {{ ?item dcterms:identifier ?id ;
                   rdfs:label ?label ;
                   prez:link ?link .
            prez:memberList a rdf:Bag ;
                    rdfs:member ?item .}}
WHERE {{ \
{chr(10) + chr(9) + f'<{item.uri}> rdfs:member ?item .' if item.uri else ""}
    ?item a <{item.children_general_class}> ;
          dcterms:identifier ?id ;
          rdfs:label|dcterms:title|skos:prefLabel ?label .
  	FILTER(DATATYPE(?id) = xsd:token)
  	BIND(CONCAT("{item.link_constructor}", STR(?id)) AS ?link)
    }} {f"LIMIT {per_page} OFFSET {(page - 1) * per_page}" if page is not None and per_page is not None else ""}
    """
    return construct_query


def generate_item_construct(item, profile: dict):
    object_uri = item.uri
    (
        include_predicates,
        exclude_predicates,
        inverse_predicates,
        sequence_predicates,
    ) = get_profile_predicates(profile, item.general_class)
    bnode_depth = profile.get("bnode_depth", 2)
    construct_query = f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n
CONSTRUCT {{
\t<{object_uri}> ?p ?o1 .
{generate_sequence_construct(object_uri, sequence_predicates) if sequence_predicates else ""} \
{f'{chr(9)}?s ?inbound_p <{object_uri}> .' if inverse_predicates else ""} \
{generate_bnode_construct(bnode_depth)} \
\n}}
WHERE {{
\t<{object_uri}> ?p ?o1 .
{generate_sequence_construct(object_uri, sequence_predicates) if sequence_predicates else chr(10)} \
{f'?s ?inbound_p <{object_uri}>{chr(10)}' if inverse_predicates else chr(10)} \
{generate_include_predicates(include_predicates)} \
{generate_inverse_predicates(inverse_predicates)} \
{generate_bnode_select(bnode_depth)}
}}
"""
    return construct_query


def generate_include_predicates(include_predicates):
    """
    Generates a SPARQL VALUES clause for a list of predicates, of the form:
    VALUES ?p { <http://example1.com> <http://example2.com> }
    """
    if include_predicates:
        return f"""VALUES ?p{{\n{chr(10).join([f"<{p}>" for p in include_predicates])}\n}}"""
    else:
        return ""


def generate_inverse_predicates(inverse_predicates):
    """
    Generates a SPARQL VALUES clause for a list of inverse predicates, of the form:
    VALUES ?inbound_p { <http://example1.com> <http://example2.com> }
    """
    if inverse_predicates:
        return f"""VALUES ?inbound_p{{\n{chr(10).join([f"<{p}>" for p in inverse_predicates])}\n}}"""
    else:
        return ""


def generate_sequence_construct(object_uri, sequence_predicates):
    """ """
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
    else:
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
        VALUES ?term {{ {" ".join('<' + term + '>' for term in uncached_terms)} }}
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
    for property in [RDFS.label, DCTERMS.description, DCTERMS.provenance]:
        cache_keys = [i for i in tbox_cache.subjects(predicate=property)]
        if cache_keys:
            cached_terms = [term for term in terms if term in cache_keys]
            uncached_terms = set(terms) - set(cached_terms)
            cached_props = [
                (term, property, tbox_cache.value(subject=term, predicate=property))
                for term in cached_terms
            ]
            [labels_from_cache.add(triple) for triple in cached_props]
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
    """
    profile_uri = profile.get("uri")
    profiles_g = create_profiles_graph()
    shape_bns = profiles_g.objects(
        subject=profile_uri,
        predicate=URIRef("http://www.w3.org/ns/dx/conneg/altr-ext#hasNodeShape"),
    )
    relevant_shape_bns = [
        sh_bn
        for sh_bn in shape_bns
        if sh_bn
        in profiles_g.subjects(
            predicate=URIRef("http://www.w3.org/ns/shacl#targetClass"),
            object=general_class,
        )
    ]
    if not relevant_shape_bns:
        return None, None, None, None
    includes = [
        i[2]
        for i in profiles_g.triples_choices(
            (relevant_shape_bns, URIRef("http://www.w3.org/ns/shacl#path"), None)
        )
    ]
    excludes = ...
    inverses = [
        i[2]
        for i in profiles_g.triples_choices(
            (relevant_shape_bns, URIRef("http://www.w3.org/ns/shacl#inversePath"), None)
        )
    ]
    sequence_nodes = [
        i[2]
        for i in profiles_g.triples_choices(
            (
                relevant_shape_bns,
                URIRef("http://www.w3.org/ns/shacl#sequencePath"),
                None,
            )
        )
    ]
    sequence_paths = [
        [path_item for path_item in profiles_g.items(i)] for i in sequence_nodes
    ]
    return includes, excludes, inverses, sequence_paths
