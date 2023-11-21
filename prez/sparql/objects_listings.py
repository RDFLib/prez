import logging
from functools import lru_cache
from itertools import chain
from textwrap import dedent
from typing import List, Optional, Tuple, Dict, FrozenSet

from rdflib import Graph, URIRef, Namespace, Literal

from prez.cache import endpoints_graph_cache, tbox_cache, profiles_graph_cache
from prez.config import settings
from prez.models import SearchMethod
from prez.models.listing import ListingModel
from prez.models.profiles_item import ProfileItem
from prez.models.profiles_listings import ProfilesMembers
from prez.reference_data.prez_ns import ONT
from prez.services.curie_functions import get_uri_for_curie_id

log = logging.getLogger(__name__)

ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
PREZ = Namespace("https://prez.dev/")


def generate_listing_construct(
    focus_item,
    profile: URIRef,
    page: Optional[int] = 1,
    per_page: Optional[int] = 20,
    ordering_predicate: URIRef = None,
):
    """
    For a given URI, finds items with the specified relation(s).
    Generates a SPARQL construct query for a listing of items
    """
    if not ordering_predicate:
        ordering_predicate = settings.label_predicates[0]

    if isinstance(focus_item, (ProfilesMembers, ListingModel)):  # listings can include
        # "context" in the same way objects can, using include/exclude predicates etc.
        (
            include_predicates,
            exclude_predicates,
            inverse_predicates,
            sequence_predicates,
        ) = get_item_predicates(profile, focus_item.selected_class)
    else:  # for objects, this context is already included in the separate "generate_item_construct" function, so these
        # predicates are explicitly set to None here to avoid duplication.
        include_predicates = (
            exclude_predicates
        ) = inverse_predicates = sequence_predicates = None
    (
        child_to_focus,
        parent_to_focus,
        focus_to_child,
        focus_to_parent,
        relative_properties,
    ) = get_listing_predicates(profile, focus_item.selected_class)
    if (
        focus_item.uri
        # and not focus_item.top_level_listing  # if it's a top level class we don't need a listing relation - we're
        # # searching by class
        and not child_to_focus
        and not parent_to_focus
        and not focus_to_child
        and not focus_to_parent
        # do not need to check relative properties - they will only be used if one of the other listing relations
        # are defined
    ):
        log.warning(
            f"Requested listing of objects related to {focus_item.uri}, however the profile {profile} does not"
            f" define any listing relations for this for this class, for example focus to child."
        )
        return None
    uri_or_tl_item = (
        "?top_level_item" if focus_item.top_level_listing else f"<{focus_item.uri}>"
    )  # set the focus

    # item to a variable if it's a top level listing (this will utilise "class based" listing, where objects are listed
    # based on them being an instance of a class), else use the URI of the "parent" off of which members will be listed.
    # TODO collapse this to an inline expression below; include change in both object and listing queries
    sequence_construct, sequence_construct_where = generate_sequence_construct(
        sequence_predicates, uri_or_tl_item
    )
    query = dedent(
        f"""
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX prez: <https://prez.dev/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        CONSTRUCT {{
            {f'{uri_or_tl_item} a <{focus_item.base_class}> .{chr(10)}' if focus_item.top_level_listing else ""}\
            {sequence_construct}
            {f'{uri_or_tl_item} ?focus_to_child ?child_item .{chr(10)}' if focus_to_child else ""}\
            {f'{uri_or_tl_item} ?focus_to_parent ?parent_item .{chr(10)}' if focus_to_parent else ""}\
            {f'?child_to_focus_s ?child_to_focus {uri_or_tl_item} .{chr(10)}' if child_to_focus else ""}\
            {f'?parent_to_focus_s ?parent_to_focus {uri_or_tl_item} .{chr(10)}' if parent_to_focus else ""}\
            {generate_relative_properties("construct", relative_properties, child_to_focus, parent_to_focus,
                                          focus_to_child, focus_to_parent)}\
            {f"{uri_or_tl_item} ?p ?o ." if include_predicates else ""}\
        }}
        WHERE {{
            {f'{uri_or_tl_item} a <{focus_item.base_class}> .{chr(10)}' if focus_item.top_level_listing else ""}\
            {f'OPTIONAL {{ {uri_or_tl_item} ?p ?o .' if include_predicates else ""}\
            {f'{generate_include_predicates(include_predicates)} }}' if include_predicates else ""} \
            {sequence_construct_where}\
            {generate_focus_to_x_predicates(uri_or_tl_item, focus_to_child, focus_to_parent)} \
            {generate_x_to_focus_predicates(uri_or_tl_item, child_to_focus, parent_to_focus)} {chr(10)} \
            {generate_relative_properties("select", relative_properties, child_to_focus, parent_to_focus,
                                          focus_to_child, focus_to_parent)}\
            {{
                SELECT ?top_level_item ?child_item
                WHERE {{
                    {f'{uri_or_tl_item} a <{focus_item.base_class}> .{chr(10)}' if focus_item.top_level_listing else generate_focus_to_x_predicates(uri_or_tl_item, focus_to_child, focus_to_parent)}\

                {f'''
                    OPTIONAL {{
                        {f'{uri_or_tl_item} <{ordering_predicate}> ?label .' if focus_item.top_level_listing else ""}
                    }}
                ''' if settings.order_lists_by_label else ""}
            }}
            {f'''
            {'ORDER BY ASC(?label)' if ordering_predicate else "ORDER BY ?top_level_item"}
            ''' if settings.order_lists_by_label else ""}
            {f"LIMIT {per_page}{chr(10)}"
             f"OFFSET {(page - 1) * per_page}" if page is not None and per_page is not None else ""}
            }}
        }}

    """
    ).strip()

    log.debug(f"Listing construct query for {focus_item} is:\n{query}")
    return query


@lru_cache(maxsize=128)
def generate_item_construct(focus_item, profile: URIRef):
    search_query = (
        True if isinstance(focus_item, SearchMethod) else False
    )  # generates a listing of search results
    (
        include_predicates,
        exclude_predicates,
        inverse_predicates,
        sequence_predicates,
    ) = get_item_predicates(profile, focus_item.selected_class)
    bnode_depth = profiles_graph_cache.value(
        profile,
        ALTREXT.hasBNodeDepth,
        None,
        default=2,
    )
    if search_query:
        uri_or_search_item = "?search_result_uri"
    else:
        uri_or_search_item = f"<{focus_item.uri}>"

    sequence_construct, sequence_construct_where = generate_sequence_construct(
        sequence_predicates, uri_or_search_item
    )

    construct_query = dedent(
        f"""    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX prez: <https://prez.dev/>
    CONSTRUCT {{
    {f'{search_query_construct()} {chr(10)}' if search_query else ""}\
    \t{uri_or_search_item} ?p ?o1 .
    {sequence_construct}
    {f'{chr(9)}?s ?inverse_predicate {uri_or_search_item} .' if inverse_predicates else ""}
    {generate_bnode_construct(bnode_depth)} \
    \n}}
    WHERE {{
        {{ {f'{focus_item.populated_query}' if search_query else ""} }}
        {{
            {uri_or_search_item} ?p ?o1 . {chr(10)} \
            {f'?s ?inverse_predicate {uri_or_search_item}{chr(10)}' if inverse_predicates else chr(10)} \
            {generate_exclude_predicates(exclude_predicates)} \
            {generate_include_predicates(include_predicates)} \
            {generate_inverse_predicates(inverse_predicates)} \
            {generate_bnode_select(bnode_depth)}\
        }}

        UNION {{
            {sequence_construct_where}\
        }}
    }}
    """
    )
    log.debug(f"Item Construct query for {uri_or_search_item} is:\n{construct_query}")
    return construct_query


def search_query_construct():
    return dedent(
        f"""?hashID a prez:SearchResult ;
        prez:searchResultWeight ?weight ;
        prez:searchResultPredicate ?predicate ;
        prez:searchResultMatch ?match ;
        prez:searchResultURI ?search_result_uri ."""
    )


def generate_relative_properties(
    construct_select,
    relative_properties,
    in_children,
    in_parents,
    out_children,
    out_parents,
):
    """
    Generate the relative properties construct or select for a listing query.
    i.e. properties on nodes related to the focus item NOT the focus item itself
    """
    if not relative_properties:
        return ""
    rel_string = ""
    kvs = {
        "ic": in_children,
        "ip": in_parents,
        "oc": out_children,
        "op": out_parents,
    }
    other_kvs = {
        "ic": "child_to_focus_s",
        "ip": "parent_to_focus_s",
        "oc": "child_item",
        "op": "parent_item",
    }
    for k, v in kvs.items():
        if v:
            if construct_select == "select":
                rel_string += f"""OPTIONAL {{ """
            rel_string += f"""?{other_kvs[k]} ?rel_{k}_props ?rel_{k}_val .\n"""
            if construct_select == "select":
                rel_string += f"""VALUES ?rel_{k}_props {{ {" ".join('<' + str(pred) + '>' for pred in relative_properties)} }} }}\n"""
    return rel_string


def generate_focus_to_x_predicates(uri_or_tl_item, focus_to_child, focus_to_parent):
    where = ""
    if focus_to_child:
        where += f"""{uri_or_tl_item} ?focus_to_child ?child_item .
        VALUES ?focus_to_child {{ {" ".join('<' + str(pred) + '>' for pred in focus_to_child)} }}\n"""
    if focus_to_parent:
        where += f"""{uri_or_tl_item} ?focus_to_parent ?parent_item .
        VALUES ?focus_to_parent {{ {" ".join('<' + str(pred) + '>' for pred in focus_to_parent)} }}\n"""
    # if not focus_to_child and not focus_to_parent:
    #     where += "VALUES ?focus_to_child {}\nVALUES ?focus_to_parent {}"
    return where


def generate_x_to_focus_predicates(uri_or_tl_item, child_to_focus, parent_to_focus):
    if not child_to_focus and not parent_to_focus:
        return ""
    where = ""
    if child_to_focus:
        where += f"""?child_to_focus_s ?child_to_focus {uri_or_tl_item} ;
        VALUES ?child_to_focus {{ {" ".join('<' + str(pred) + '>' for pred in child_to_focus)} }}\n"""
    if parent_to_focus:
        where += f"""?parent_to_focus_s ?parent_to_focus {uri_or_tl_item} ;
        VALUES ?parent_to_focus {{ {" ".join('<' + str(pred) + '>' for pred in parent_to_focus)} }}\n"""
    # if not child_to_focus and not parent_to_focus:
    #     where += "VALUES ?child_to_focus {}\nVALUES ?parent_to_focus {}"
    return where


def generate_include_predicates(include_predicates):
    """
    Generates a SPARQL VALUES clause for a list of predicates, of the form:
    VALUES ?p { <http://example1.com> <http://example2.com> }
    """
    if include_predicates:
        return f"""VALUES ?p{{\n{chr(10).join([f"<{p}>" for p in include_predicates])}\n}}"""
    return ""


def generate_exclude_predicates(exclude_predicates):
    if exclude_predicates:
        return f"""FILTER(?p NOT IN ({chr(10).join([f"<{p}>" for p in exclude_predicates])}))"""
    return ""


def generate_inverse_predicates(inverse_predicates):
    """
    Generates a SPARQL VALUES clause for a list of inverse predicates, of the form:
    VALUES ?inverse_predicate { <http://example1.com> <http://example2.com> }
    """
    if inverse_predicates:
        return f"""VALUES ?inverse_predicate{{\n{chr(10).join([f"<{p}>" for p in inverse_predicates])}\n}}"""
    return ""


def _generate_sequence_construct(object_uri, sequence_predicates, path_n=0):
    """
    Generates part of a SPARQL CONSTRUCT query for property paths, given a list of lists of property paths.
    """
    if sequence_predicates:
        all_sequence_construct = ""
        for predicate_list in sequence_predicates:
            construct_and_where = (
                f"\t{object_uri} <{predicate_list[0]}> ?seq_o1_{path_n} ."
            )
            for i in range(1, len(predicate_list)):
                construct_and_where += f"\n\t?seq_o{i}_{path_n} <{predicate_list[i]}> ?seq_o{i + 1}_{path_n} ."
            all_sequence_construct += construct_and_where
        return all_sequence_construct
    return ""


def generate_sequence_construct(
    sequence_predicates: list[list[URIRef]], uri_or_tl_item: str
) -> tuple[str, str]:
    sequence_construct = ""
    sequence_construct_where = ""
    if sequence_predicates:
        for i, sequence_predicate in enumerate(sequence_predicates):
            seq_partial_str = "OPTIONAL {\n"
            generate_sequence_construct_result: str = _generate_sequence_construct(
                uri_or_tl_item, [sequence_predicate], i
            )
            seq_partial_str += generate_sequence_construct_result
            seq_partial_str += "\n}\n"
            sequence_construct_where += seq_partial_str
            sequence_construct += generate_sequence_construct_result

    return sequence_construct, sequence_construct_where


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
):
    """
    Gets annotation data used for HTML display.
    This includes the label, description, and provenance, if available.
    Note the following three default predicates are always included. This allows context, i.e. background ontologies,
    which are often diverse in the predicates they use, to be aligned with the default predicates used by Prez. The full
    range of predicates used can be manually included via profiles.
    """
    label_predicates = settings.label_predicates
    description_predicates = settings.description_predicates
    explanation_predicates = settings.provenance_predicates
    other_predicates = settings.other_predicates
    terms = (
        set(i for i in item_graph.predicates() if isinstance(i, URIRef))
        | set(i for i in item_graph.objects() if isinstance(i, URIRef))
        | set(i for i in item_graph.subjects() if isinstance(i, URIRef))
    )
    # TODO confirm caching of SUBJECT labels does not cause issues! this could be a lot of labels. Perhaps these are
    # better separated and put in an LRU cache. Or it may not be worth the effort.
    if not terms:
        return None, Graph()
    # read labels from the tbox cache, this should be the majority of labels
    uncached_terms, labels_g = get_annotations_from_tbox_cache(
        terms,
        label_predicates,
        description_predicates,
        explanation_predicates,
        other_predicates,
    )

    def other_predicates_statement(other_predicates, uncached_terms_other):
        return f"""UNION
            {{
                ?unannotated_term ?other_prop ?other .
                VALUES ?other_prop {{ {" ".join('<' + str(pred) + '>' for pred in other_predicates)} }}
                VALUES ?unannotated_term {{ {" ".join('<' + str(term) + '>' for term in uncached_terms_other)}
                }}
            }}"""

    queries_for_uncached = f"""CONSTRUCT {{
    ?unlabeled_term ?label_prop ?label .
    ?undescribed_term ?desc_prop ?description .
    ?unexplained_term ?expl_prop ?explanation .
    ?unannotated_term ?other_prop ?other .
    }}
        WHERE {{
            {{
                ?unlabeled_term ?label_prop ?label .
                VALUES ?label_prop {{ {" ".join('<' + str(pred) + '>' for pred in label_predicates)} }}
                VALUES ?unlabeled_term {{ {" ".join('<' + str(term) + '>' for term in uncached_terms["labels"])} }}
                FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
            }}
            UNION
            {{
                ?undescribed_term ?desc_prop ?description .
                VALUES ?desc_prop {{ {" ".join('<' + str(pred) + '>' for pred in description_predicates)} }}
                VALUES ?undescribed_term {{ {" ".join('<' + str(term) + '>' for term in uncached_terms["descriptions"])}
                }}
            }}
            UNION
            {{
                ?unexplained_term ?expl_prop ?explanation .
                VALUES ?expl_prop {{ {" ".join('<' + str(pred) + '>' for pred in explanation_predicates)} }}
                VALUES ?unexplained_term {{ {" ".join('<' + str(term) + '>' for term in uncached_terms["provenance"])}
                }}
            }}
            {other_predicates_statement(other_predicates, uncached_terms["other"]) if other_predicates else ""}
        }}"""
    return queries_for_uncached, labels_g


def get_annotations_from_tbox_cache(
    terms: List[URIRef], label_props, description_props, explanation_props, other_props
):
    """
    Gets labels from the TBox cache, returns a list of terms that were not found in the cache, and a graph of labels,
    descriptions, and explanations
    """
    labels_from_cache = Graph(bind_namespaces="rdflib")
    terms_list = list(terms)
    props_from_cache = {
        "labels": list(
            chain(
                *(
                    tbox_cache.triples_choices((terms_list, prop, None))
                    for prop in label_props
                )
            )
        ),
        "descriptions": list(
            chain(
                *(
                    tbox_cache.triples_choices((terms_list, prop, None))
                    for prop in description_props
                )
            )
        ),
        "provenance": list(
            chain(
                *(
                    tbox_cache.triples_choices((terms_list, prop, None))
                    for prop in explanation_props
                )
            )
        ),
        "other": list(
            chain(
                *(
                    tbox_cache.triples_choices((terms_list, prop, None))
                    for prop in other_props
                )
            )
        ),
    }
    # get all the annotations we can from the cache
    all = list(chain(*props_from_cache.values()))
    for triple in all:
        labels_from_cache.add(triple)
    # the remaining terms are not in the cache; we need to query the SPARQL endpoint to attempt to get them
    uncached_props = {
        k: list(set(terms) - set(triple[0] for triple in v))
        for k, v in props_from_cache.items()
    }
    return uncached_props, labels_from_cache


# hit the count cache first, if it's not there, hit the SPARQL endpoint
def generate_listing_count_construct(item: ListingModel, endpoint_uri: str):
    """
    Generates a SPARQL construct query to count either:
    1. the members of a collection, if a URI is given, or;
    2. the number of instances of a base class, given a base class.
    """
    if not item.top_level_listing:
        # count based on relation to a parent object - first find the relevant parent->child or child->parent relation
        # from the endpoint definition.
        p2f_relation = endpoints_graph_cache.value(
            subject=URIRef(endpoint_uri), predicate=ONT.ParentToFocusRelation
        )
        f2p_relation = endpoints_graph_cache.value(
            subject=URIRef(endpoint_uri), predicate=ONT.FocusToParentRelation
        )
        assert p2f_relation or f2p_relation, (
            f"Endpoint {endpoint_uri} does not have a parent to focus or focus to "
            f"parent relation defined."
        )
        p2f_statement = f"<{item.uri}> <{p2f_relation}> ?item ." if p2f_relation else ""
        f2p_statement = f"?item <{f2p_relation}> <{item.uri}> ." if f2p_relation else ""
        query = dedent(
            f"""
            PREFIX prez: <https://prez.dev/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT {{ <{item.uri}> prez:count ?count }}
            WHERE {{
                SELECT (COUNT(?item) as ?count)
                WHERE {{
                        {p2f_statement}
                        {f2p_statement}
                }}
            }}"""
        ).strip()
        return query
    else:  # item.selected_class
        query = dedent(
            f"""
            PREFIX prez: <https://prez.dev/>

            CONSTRUCT {{ <{item.base_class}> prez:count ?count }}
            WHERE {{
                SELECT (COUNT(?item) as ?count)
                WHERE {{
                        ?item a <{item.base_class}> .
                }}
            }}"""
        ).strip()
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
    - child to focus, for example where the object of interest is a Concept Scheme, and is linked to Concept(s) via
        the predicate skos:inScheme
    - focus to child, for example where the object of interest is a Feature Collection, and is linked to Feature(s)
        via the predicate rdfs:member
    - parent to focus, for example where the object of interest is a Feature Collection, and is linked to Dataset(s) via
        the predicate dcterms:hasPart
    - focus to parents, for example where the object of interest is a Concept, and is linked to Concept Scheme(s) via
    the predicate skos:inScheme
    - relative properties, properties of the parent/child objects that should also be returned. For example, if the
        focus object is a Concept Scheme, and the predicate skos:inScheme is used to link from Concept(s) (using
        altr-ext:childToFocus) then specifying skos:broader as a relative property will cause the broader concepts to
        be returned for each concept
    """
    shape_bns = get_relevant_shape_bns_for_profile(selected_class, profile)
    if not shape_bns:
        return [], [], [], [], []
    child_to_focus = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.childToFocus,
                None,
            )
        )
    ]
    parent_to_focus = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.parentToFocus,
                None,
            )
        )
    ]
    focus_to_child = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.focusToChild,
                None,
            )
        )
    ]
    focus_to_parent = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.focusToParent,
                None,
            )
        )
    ]
    relative_properties = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (
                shape_bns,
                ALTREXT.relativeProperties,
                None,
            )
        )
    ]
    return (
        child_to_focus,
        parent_to_focus,
        focus_to_child,
        focus_to_parent,
        relative_properties,
    )


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
        log.info(
            f"No special predicates (include/exclude/inverse/sequence) found for class {selected_class} in profile "
            f"{profile}. Default behaviour is to include all predicates, and blank nodes to a depth of two."
        )
        return None, None, None, None
    includes = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (shape_bns, URIRef("http://www.w3.org/ns/shacl#path"), None)
        )
    ]
    excludes = [
        i[2]
        for i in profiles_graph_cache.triples_choices(
            (shape_bns, ALTREXT.exclude, None)
        )
    ]
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
    requested_profile_uri: URIRef = None,
    requested_profile_token: str = None,
    requested_mediatypes: List[Tuple] = None,
):
    """
    Returns a SPARQL SELECT query which will determine the profile and mediatype to return based on user requests,
    defaults, and the availability of these in profiles.

    NB: Most specific class refers to the rdfs:Class of an object which has the most specific rdfs:subClassOf links to
    the base class delivered by that API endpoint. The base classes delivered by each API endpoint are:

    SpacePrez:
    /s/datasets -> prez:DatasetList
    /s/datasets/{ds_id} -> dcat:Dataset
    /s/datasets/{ds_id}/collections/{fc_id} -> geo:FeatureCollection
    /s/datasets/{ds_id}/collections -> prez:FeatureCollectionList
    /s/datasets/{ds_id}/collections/{fc_id}/features -> geo:Feature

    VocPrez:
    /v/schemes -> skos:ConceptScheme
    /v/collections -> skos:Collection
    /v/schemes/{cs_id}/concepts -> skos:Concept

    CatPrez:
    /c/catalogs -> dcat:Catalog
    /c/catalogs/{cat_id}/datasets -> dcat:Dataset

    The following logic is used to determine the profile and mediatype to be returned:

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
    if requested_profile_token:
        requested_profile_uri = get_uri_for_curie_id(requested_profile_token)
    query = dedent(
        f"""    PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX geo: <http://www.opengis.net/ont/geosparql#>
    PREFIX prez: <https://prez.dev/>
    PREFIX prof: <http://www.w3.org/ns/dx/prof/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>

    SELECT ?profile ?title ?class (count(?mid) as ?distance) ?req_profile ?def_profile ?format ?req_format ?def_format

    WHERE {{
      VALUES ?class {{{" ".join('<' + str(klass) + '>' for klass in classes)}}}
      ?class rdfs:subClassOf* ?mid .
      ?mid rdfs:subClassOf* ?base_class .
      VALUES ?base_class {{ dcat:Dataset geo:FeatureCollection prez:FeatureCollectionList prez:FeatureList geo:Feature
      skos:ConceptScheme skos:Concept skos:Collection prez:DatasetList prez:VocPrezCollectionList prez:SchemesList
      prez:CatalogList prez:ResourceList prez:ProfilesList dcat:Catalog dcat:Resource prof:Profile prez:SPARQLQuery 
      prez:SearchResult }}
      ?profile altr-ext:constrainsClass ?class ;
               altr-ext:hasResourceFormat ?format ;
               dcterms:title ?title .\
      {f'BIND(?profile=<{requested_profile_uri}> as ?req_profile)' if requested_profile_uri else ''}
      BIND(EXISTS {{ ?shape sh:targetClass ?class ;
                           altr-ext:hasDefaultProfile ?profile }} AS ?def_profile)
      {generate_mediatype_if_statements(requested_mediatypes) if requested_mediatypes else ''}
      BIND(EXISTS {{ ?profile altr-ext:hasDefaultResourceFormat ?format }} AS ?def_format)
    }}
    GROUP BY ?class ?profile ?req_profile ?def_profile ?format ?req_format ?def_format ?title
    ORDER BY DESC(?req_profile) DESC(?distance) DESC(?def_profile) DESC(?req_format) DESC(?def_format)"""
    )
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
        f"""{line_join.join({chr(9) + 'IF(?format="' + tup[1] + '", "' + str(tup[0]) + '"' for tup in requested_mediatypes})}"""
        f""", ""{')' * len(requested_mediatypes)}\n"""
        f"\tAS ?req_format)"
    )
    return ifs


def get_endpoint_template_queries(classes: FrozenSet[URIRef]):
    """
    NB the FILTER clause here should NOT be required but RDFLib has a bug (perhaps related to the +/* operators -
    requires further investigation). Removing the FILTER clause will return too many results in instances where there
    should be NO results - as if the VALUES ?classes clause is not used.
    """
    query = f"""
    PREFIX ont: <https://prez.dev/ont/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    SELECT ?endpoint ?parent_endpoint ?relation_direction ?relation_predicate ?endpoint_template ?distance
    {{
    VALUES ?classes {{ {" ".join('<' + str(klass) + '>' for klass in classes)} }}
      {{
      ?endpoint a ont:ObjectEndpoint ;
      ont:endpointTemplate ?endpoint_template ;
      ont:deliversClasses ?classes .
      BIND("0"^^xsd:integer AS ?distance)
      }}
        UNION
      {{
      ?endpoint ?relation_direction ?relation_predicate ;
        ont:endpointTemplate ?endpoint_template ;
        ont:deliversClasses ?classes .
  		FILTER(?classes IN ({", ".join('<' + str(klass) + '>' for klass in classes)}))
        VALUES ?relation_direction {{ont:FocusToParentRelation ont:ParentToFocusRelation}}
          {{ SELECT ?parent_endpoint ?endpoint (count(?intermediate) as ?distance)
            {{
              ?endpoint ont:parentEndpoint+ ?intermediate ;
                  ont:deliversClasses ?classes .
              ?intermediate ont:parentEndpoint* ?parent_endpoint .
              ?intermediate a ?intermediateEPClass .
              ?parent_endpoint a ?parentEPClass .
              VALUES ?intermediateEPClass {{ont:ObjectEndpoint}}
              VALUES ?parentEPClass {{ont:ObjectEndpoint}}
            }}
            GROUP BY ?parent_endpoint ?endpoint
            
          }}
      }}
    }} ORDER BY DESC(?distance)
    """
    return query


def generate_relationship_query(
    uri: URIRef, endpoint_to_relations: Dict[URIRef, List[Tuple[URIRef, Literal]]]
):
    """
    Generates a SPARQL query of the form:
    SELECT * {{ SELECT ?endpoint ?parent_1 ?parent_2
        WHERE {
    BIND("/s/datasets/$parent_1/collections/$object" as ?endpoint)
    ?parent_1 <http://www.w3.org/2000/01/rdf-schema#member> <https://test/feature-collection> .
    }}}
    """
    if not endpoint_to_relations:
        return None
    subqueries = []
    for endpoint, relations in endpoint_to_relations.items():
        subquery = f"""{{ SELECT ?endpoint {" ".join(["?parent_" + str(i + 1) for i, _ in enumerate(relations)])}
        WHERE {{\n BIND("{endpoint}" as ?endpoint)\n"""
        uri_str = f"<{uri}>"
        for i, relation in enumerate(relations):
            predicate, direction = relation
            parent = "?parent_" + str(i + 1)
            if predicate:
                if direction == URIRef("https://prez.dev/ont/ParentToFocusRelation"):
                    subquery += f"{parent} <{predicate}> {uri_str} .\n"
                else:  # assuming the direction is "focus_to_parent"
                    subquery += f"{uri_str} <{predicate}> {parent} .\n"
            uri_str = parent
        subquery += "}}"
        subqueries.append(subquery)

    union_query = "SELECT * {" + " UNION ".join(subqueries) + "}"
    return union_query


def startup_count_objects():
    """
    Retrieves hardcoded counts for collections in the dataset (feature collections, datasets etc.)
    """
    return f"""PREFIX prez: <https://prez.dev/>
CONSTRUCT {{ ?collection prez:count ?count }}
WHERE {{ ?collection prez:count ?count }}"""
