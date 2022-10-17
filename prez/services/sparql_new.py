from typing import List, Optional

from rdflib import Graph, URIRef, RDFS, DCTERMS
from rdflib.graph import BatchAddGraph

from prez.cache import tbox_cache, missing_annotations


def generate_listing_construct(
    item_class: URIRef,
    parent_uri: URIRef,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    profile: dict = {},  # unused - we don't currently filter or otherwise change listings based on profiles
):
    """
    Generates a SPARQL construct query for a listing of items, including labels
    """
    construct_query = f"""PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>

CONSTRUCT {{ ?item dcterms:identifier ?id ;
                   rdfs:label ?label ; }}
WHERE {{ \
{chr(10) + chr(9) + f'<{parent_uri}> rdfs:member ?item .' if parent_uri else ""}
    ?item a <{item_class}> ;
          dcterms:identifier ?id ;
          rdfs:label|dcterms:title|skos:prefLabel ?label .
  	FILTER(DATATYPE(?id) = xsd:token)
    }} {f"LIMIT {per_page} OFFSET {(page - 1) * per_page}" if page is not None and per_page is not None else ""}
    """
    return construct_query


def generate_item_construct(object_uri: URIRef, profile: dict):
    include_predicates = []  # TODO from profile
    exclude_predicates = []  # TODO from profile
    bnode_depth = profile.get("bnode_depth", 2)  # TODO from profile
    construct_query = f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n
CONSTRUCT {{
    <{object_uri}> ?p ?o1 .
{generate_bnode_construct(bnode_depth)}
  }}
WHERE {{
    <{object_uri}> !rdfs:member ?o1 ;
        ?p ?o1 . \n
{generate_include_predicates(include_predicates)} \
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


def generate_bnode_construct(depth):
    """
    Generate the construct query for the bnodes, this is of the form:
    ?o1 ?p2 ?o2 .
        ?o2 ?p3 ?o3 .
        ...
    """
    return "\n".join([f"\t?o{i + 1} ?p{i + 2} ?o{i + 2} ." for i in range(depth)])


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
    # read labels from the tbox cache, this should be the majority of labels
    uncached_terms, labels_g = get_annotations_from_tbox_cache(terms)
    # read remaining labels from the SPARQL endpoint
    queries_for_uncached = [
        f"""CONSTRUCT {{ <{term}> <{label_property}> ?label }}
WHERE {{ <{term}> <{label_property}> ?label
FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
}}"""
        for term in uncached_terms
    ]
    # remove any queries we previously didn't get a result for from the SPARQL endpoint
    queries_for_uncached = list(set(queries_for_uncached) - set(missing_annotations))
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
        query_explicit = f"""PREFIX prez: <https://surroundaustralia.com/prez/>

CONSTRUCT {{ <{collection_uri}> prez:count ?count }}
WHERE {{ <{collection_uri}> prez:count ?count }}"""

        query_implicit = f"""PREFIX prez: <https://surroundaustralia.com/prez/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CONSTRUCT {{ <{collection_uri}> prez:count ?count }}
WHERE {{
    SELECT (COUNT(?item) as ?count) {{
        <{collection_uri}> rdfs:member ?item .
    }}
}}"""
        return query_explicit, query_implicit
    else:  # general_class
        return f"""PREFIX prez: <https://surroundaustralia.com/prez/>

CONSTRUCT {{ <{general_class}> prez:count ?count }}
WHERE {{
    SELECT (COUNT(?item) as ?count) {{
        ?item a <{general_class}> .
    }}
}}"""
