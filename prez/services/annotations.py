import logging
from itertools import chain
from textwrap import dedent
from typing import List, Tuple

from rdflib import Graph, URIRef, Namespace, Literal

from prez.cache import tbox_cache
from prez.config import settings
from prez.services.curie_functions import get_uri_for_curie_id

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
