import logging
from functools import lru_cache
from itertools import chain
from textwrap import dedent
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


def generate_listing_construct_from_uri(
        focus_item,
        profile,
        page: Optional[int] = 1,
        per_page: Optional[int] = 20,
):
    """
    For a given URI, finds items with the specified relation(s).
    Generates a SPARQL construct query for a listing of items
    #TODO update to use either URI or class, as specified in the function signature. Class will be used for alternate profiles - although the URI is known in this case, profiles constrain the class.
    """
    (
        inbound_children,
        inbound_parents,
        outbound_children,
        outbound_parents,
        relative_properties,
    ) = get_listing_predicates(profile, focus_item.selected_class)
    if (
            focus_item.uri
            and not inbound_children
            and not inbound_parents
            and not outbound_children
            and not outbound_parents
            # do not need to check relative properties - they will only be used if one of the inbound/outbound parent/child
            # relations are defined
    ):
        log.warning(
            f"Requested listing of objects related to {focus_item.uri}, however the profile {profile} does not"
            f" define any listing relations for this for this class, for example outbound children."
        )
        return None
    query = dedent(
        f"""
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX prez: <https://prez.dev/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        CONSTRUCT {{
            {f'<{focus_item.uri}> ?outbound_children ?child_item .{chr(10)}' if outbound_children else ""}\
            {f'<{focus_item.uri}> ?outbound_parents ?parent_item .{chr(10)}' if outbound_parents else ""}\
            {f'?inbound_child_s ?inbound_child <{focus_item.uri}> ;{chr(10)}' if inbound_children else ""}\
            {f'?inbound_parent_s ?inbound_parent <{focus_item.uri}> ;{chr(10)}' if inbound_parents else ""}\
            {generate_relative_properties("construct", relative_properties, inbound_children, inbound_parents, outbound_children,
                                          outbound_parents)}\
        }}
        WHERE {{
            {generate_outbound_predicates(focus_item, outbound_children, outbound_parents)} \
            {generate_inbound_predicates(focus_item, inbound_children, inbound_parents)} {chr(10)} \
            {generate_relative_properties("select", relative_properties, inbound_children, inbound_parents, outbound_children,
                                          outbound_parents)}\
        }}
        {f"LIMIT {per_page}{chr(10)}"
         f"        OFFSET {(page - 1) * per_page}" if page is not None and per_page is not None else ""}
    """
    ).strip()
    log.debug(f"Listing construct query for {focus_item} is:\n{query}")
    predicates_for_link_addition = {"link_constructor": focus_item.link_constructor,
                                    "parent": inbound_parents + outbound_parents,
                                    "child": outbound_children + inbound_children}
    return query, predicates_for_link_addition


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
    construct_query = dedent(
        f"""PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX prez: <https://prez.dev/>
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
        MINUS {{ <{object_uri}> dcterms:identifier ?o1 .
                FILTER(DATATYPE(?o1)=prez:slug) }} \
    }}
    """
    )
    log.debug(f"Item Construct query for {object_uri} is:\n{construct_query}")
    return construct_query


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
        "ic": "inbound_child_s",
        "ip": "inbound_parent_s",
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


def generate_outbound_predicates(item, outbound_children, outbound_parents):
    where = ""
    if item.uri:
        if outbound_children:
            where += f"""<{item.uri}> ?outbound_children ?child_item .
            VALUES ?outbound_children {{ {" ".join('<' + str(pred) + '>' for pred in outbound_children)} }}\n"""
        if outbound_parents:
            where += f"""<{item.uri}> ?outbound_parents ?parent_item .
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
        VALUES ?inbound_child {{ {" ".join('<' + str(pred) + '>' for pred in inbound_children)} }}\n"""
    if inbound_parents:
        where += f"""?inbound_parent_s ?inbound_parent <{item.uri}> ;
        VALUES ?inbound_parent {{ {" ".join('<' + str(pred) + '>' for pred in inbound_parents)} }}\n"""
    # if not inbound_children and not inbound_parents:
    #     where += "VALUES ?inbound_child {}\nVALUES ?inbound_parent {}"
    return where


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
        label_predicates: List[URIRef],
        description_predicates: List[URIRef],
        explanation_predicates: List[URIRef],
):
    """
    Gets annotation data used for HTML display.
    This includes the label, description, and provenance, if available.
    Note the following three default predicates are always included. This allows context, i.e. background ontologies,
    which are often diverse in the predicates they use, to be aligned with the default predicates used by Prez. The full
    range of predicates used can be manually included via profiles.
    """
    label_predicates += [RDFS.label]
    description_predicates += [DCTERMS.description]
    explanation_predicates += [DCTERMS.provenance]
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
        terms, label_predicates, description_predicates, explanation_predicates
    )
    queries_for_uncached = f"""CONSTRUCT {{
    ?unlabeled_term ?label_prop ?label .
    ?undescribed_term ?desc_prop ?description .
    ?unexplained_term ?expl_prop ?explanation . }}
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
        }}"""
    return queries_for_uncached, labels_g


def get_annotations_from_tbox_cache(
        terms: List[URIRef], label_props, description_props, explanation_props
):
    """
    Gets labels from the TBox cache, returns a list of terms that were not found in the cache, and a graph of labels,
    descriptions, and explanations
    """
    labels_from_cache = Graph(bind_namespaces="rdflib")
    terms_list = list(terms)
    # triples = []
    # triples = list(chain(*(tbox_cache.triples_choices((terms_list, predicate, None)) for predicate in predicates)))
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
    }
    all = list(chain(*props_from_cache.values()))
    for triple in all:
        labels_from_cache.add(triple)
    uncached_props = {
        k: list(set(terms) - set(triple[0] for triple in v))
        for k, v in props_from_cache.items()
    }
    return uncached_props, labels_from_cache


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
        query = dedent(
            f"""
            PREFIX prez: <https://prez.dev/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT {{ <{item.uri}> prez:count ?count }}
            WHERE {{
                SELECT (COUNT(?item) as ?count)
                WHERE {{
                    GRAPH ?g {{
                        <{item.uri}> rdfs:member ?item .
                    }}
                }}
            }}"""
        ).strip()
        return query
    else:  # item.selected_class
        query = dedent(
            f"""
            PREFIX prez: <https://prez.dev/>

            CONSTRUCT {{ <{item.general_class}> prez:count ?count }}
            WHERE {{
                SELECT (COUNT(?item) as ?count)
                WHERE {{
                    GRAPH ?g {{
                        ?item a <{item.general_class}> .
                    }}
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


def get_annotation_predicates(profile):
    """
    Gets the annotation predicates from the profiles graph for a given profile.
    If no predicates are found, "None" is returned by RDFLib
    """
    preds = {
        "label_predicates": [],
        "description_predicates": [],
        "explanation_predicates": [],
    }
    if not profile:
        return preds
    preds["label_predicates"].extend(
        list(
            profiles_graph_cache.objects(
                subject=profile, predicate=ALTREXT.hasLabelPredicate
            )
        )
    )
    preds["description_predicates"].extend(
        list(
            profiles_graph_cache.objects(
                subject=profile, predicate=ALTREXT.hasDescriptionPredicate
            )
        )
    )
    preds["explanation_predicates"].extend(
        list(
            profiles_graph_cache.objects(
                subject=profile, predicate=ALTREXT.hasExplanationPredicate
            )
        )
    )
    if not bool(
            list(chain(*preds.values()))
    ):  # check whether any predicates were found
        log.info(
            f"No annotation predicates found for profile {profile}, defaults will be used:\n"
            f"Label: rdfs:label; Description: dcterms:description; Explanation: dcterms:provenance.\n"
            f"To specify annotation predicates (to be used in *addition* to the defaults), use the following "
            f"predicates in a profile definition: altrext:hasLabelPredicate, altrext:hasDescriptionPredicate, "
            f"altrext:hasExplanationPredicate"
        )
    return preds


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
    - relative properties, properties of the parent/child objects that should also be returned. For example, if the
        focus object is a Concept Scheme, and the predicate skos:inScheme is used to link from Concept(s) (using
        altr-ext:inboundChildren) then specifying skos:broader as a relative property will cause the broader concepts to
        be returned for each concept
    """
    shape_bns = get_relevant_shape_bns_for_profile(selected_class, profile)
    if not shape_bns:
        return [], [], [], [], []
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
        inbound_children,
        inbound_parents,
        outbound_children,
        outbound_parents,
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
        requested_profile_uri: URIRef = None,
        requested_profile_token: str = None,
        requested_mediatypes: List[Tuple] = None,
):
    """
    Returns a SPARQL SELECT query which will determine the profile and mediatype to return based on user requests,
    defaults, and the availability of these in profiles.

    NB: Most specific class refers to the rdfs:Class of an object which has the most specific rdfs:subClassOf links to
    the general class delivered by that API endpoint. The general classes delivered by each API endpoint are:

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

    SELECT ?profile ?title ?class (count(?mid) as ?distance) ?req_profile ?def_profile ?format ?req_format ?def_format ?token

    WHERE {{
      VALUES ?class {{{" ".join('<' + str(klass) + '>' for klass in classes)}}}
      ?class rdfs:subClassOf* ?mid .
      ?mid rdfs:subClassOf* ?general_class .
      VALUES ?general_class {{ dcat:Dataset geo:FeatureCollection prez:FeatureCollectionList prez:FeatureList geo:Feature
      skos:ConceptScheme skos:Concept skos:Collection prez:DatasetList prez:VocPrezCollectionList prez:SchemesList
      prez:CatalogList dcat:Catalog dcat:Resource prez:ProfilesList prof:Profile prez:SpacePrezProfileList
      prez:VocPrezProfileList prez:CatPrezProfileList }}
      ?profile altr-ext:constrainsClass ?class ;
               altr-ext:hasResourceFormat ?format ;
               dcterms:identifier ?token ;
               dcterms:title ?title .\
      {f'BIND(?profile=<{requested_profile_uri}> as ?req_profile)' if requested_profile_uri else ''}
      {f'BIND(?token="{requested_profile_token}" as ?req_profile)' if requested_profile_token else ''}
      BIND(EXISTS {{ ?shape sh:targetClass ?class ;
                           altr-ext:hasDefaultProfile ?profile }} AS ?def_profile)
      {generate_mediatype_if_statements(requested_mediatypes) if requested_mediatypes else ''}
      BIND(EXISTS {{ ?profile altr-ext:hasDefaultResourceFormat ?format }} AS ?def_format)
      # FILTER(DATATYPE(?token)=prez:slug)
    }}
    GROUP BY ?class ?profile ?req_profile ?def_profile ?format ?req_format ?def_format ?title ?token
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


def startup_count_objects():
    """
    Retrieves hardcoded counts for collections in the dataset (feature collections, datasets etc.)
    """
    return f"""PREFIX prez: <https://prez.dev/>
CONSTRUCT {{ ?collection prez:count ?count }}
WHERE {{ ?collection prez:count ?count }}"""
