import logging
from itertools import chain
from textwrap import dedent
from typing import List, Tuple, Dict, FrozenSet

from rdflib import Graph, URIRef, Namespace, Literal

from prez.cache import tbox_cache, profiles_graph_cache
from prez.config import settings
from prez.services.curie_functions import get_uri_for_curie_id
from temp.grammar.grammar import SubSelect

log = logging.getLogger(__name__)

ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
PREZ = Namespace("https://prez.dev/")


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
    default_language = settings.default_language
    for triple in all:
        if isinstance(triple[2], Literal):
            if triple[2].language == default_language:
                labels_from_cache.add(triple)
            elif triple[2].language is None:
                labels_from_cache.add(triple)
    # the remaining terms are not in the cache; we need to query the SPARQL endpoint to attempt to get them
    uncached_props = {
        k: list(set(terms) - set(triple[0] for triple in v))
        for k, v in props_from_cache.items()
    }
    return uncached_props, labels_from_cache


def temp_listing_count(subquery: SubSelect, klass):
    """
    TODO: Implement COUNT and other expressions in SPARQL grammar.
    """
    return f"""
    PREFIX prez: <{PREZ}>
    CONSTRUCT {{
     {klass.n3()} prez:count ?count
    }}
    WHERE {{
      SELECT (COUNT(DISTINCT ?focus_node) as ?count) {{ {subquery} }}
    }}"""


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
    listing: bool = False,
):
    """
    Returns a SPARQL SELECT query which will determine the profile and mediatype to return based on user requests,
    defaults, and the availability of these in profiles.

    NB: Most specific class refers to the rdfs:Class of an object which has the most specific rdfs:subClassOf links to
    the base class delivered by that API endpoint. The base classes delivered by each API endpoint are:

    SpacePrez:
    /s/catalogs -> prez:DatasetList
    /s/catalogs/{ds_id} -> dcat:Dataset
    /s/catalogs/{ds_id}/collections/{fc_id} -> geo:FeatureCollection
    /s/catalogs/{ds_id}/collections -> prez:FeatureCollectionList
    /s/catalogs/{ds_id}/collections/{fc_id}/features -> geo:Feature

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
    if listing:
        profile_class = PREZ.ListingProfile
    else:
        profile_class = PREZ.ObjectProfile
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
      VALUES ?base_class {{ dcat:Dataset geo:FeatureCollection geo:Feature
      skos:ConceptScheme skos:Concept skos:Collection 
      prez:ProfilesList dcat:Catalog dcat:Resource prof:Profile prez:SPARQLQuery 
      prez:SearchResult prez:CQLObjectList prez:QueryablesList prez:Object }}
      ?profile altr-ext:constrainsClass ?class ;
               altr-ext:hasResourceFormat ?format ;
               dcterms:title ?title .\
      {f'?profile a {profile_class.n3()} .'}
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
      ?parent_endpoint ?relation_direction ?relation_predicate .
      ?endpoint ?ep_relation_direction ?ep_relation_predicate ;
        ont:endpointTemplate ?endpoint_template ;
        ont:deliversClasses ?classes .
  		FILTER(?classes IN ({", ".join('<' + str(klass) + '>' for klass in classes)}))
        VALUES ?relation_direction {{ont:focusToParentRelation ont:parentToFocusRelation}}
        VALUES ?ep_relation_direction {{ont:focusToParentRelation ont:parentToFocusRelation}}
          {{ SELECT ?parent_endpoint ?endpoint (count(?intermediate) as ?distance)
            {{
              ?endpoint ont:parentEndpoint* ?intermediate ;
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
    }} ORDER BY ASC(?distance)
    """
    return query


def generate_relationship_query(
    uri: URIRef, endpoint_to_relations: Dict[URIRef, List[Tuple[URIRef, Literal]]]
):
    """
    Generates a SPARQL query of the form:
    SELECT * {{ SELECT ?endpoint ?parent_1 ?parent_2
        WHERE {
    BIND("/s/catalogs/$parent_1/collections/$object" as ?endpoint)
    ?parent_1 <http://www.w3.org/2000/01/rdf-schema#member> <https://test/feature-collection> .
    }}}
    """
    if not endpoint_to_relations:
        return None
    subqueries = []
    for endpoint, relations in endpoint_to_relations.items():
        subquery = f"""{{ SELECT ?endpoint {" ".join(["?parent_" + str(i + 1) for i, pred in enumerate(relations)])}
        WHERE {{\n BIND("{endpoint}" as ?endpoint)\n"""
        uri_str = f"<{uri}>"
        for i, relation in enumerate(relations):
            predicate, direction = relation
            if predicate:
                parent = "?parent_" + str(i)
                if direction == URIRef("https://prez.dev/ont/parentToFocusRelation"):
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
