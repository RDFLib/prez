import logging
from typing import List, FrozenSet, Set

from aiocache import caches
from rdflib import Graph, URIRef, Literal

from prez.dependencies import get_annotations_repo
from prez.repositories import Repo
from prez.services.query_generation.annotations import (
    AnnotationsConstructQuery,
)
from temp.grammar import *

log = logging.getLogger(__name__)

pred = IRI(value=URIRef("https://prez.dev/label"))

caches.set_config(
    {
        "default": {
            "cache": "aiocache.SimpleMemoryCache",
            "serializer": {"class": "aiocache.serializers.PickleSerializer"},
        }
    }
)


async def process_terms(terms_and_dtypes: Set[URIRef], repo: Repo, system_repo: Repo):
    """
    This function processes the terms and their data types. It first retrieves the cached results for the given terms
    and data types. Then, it processes the terms that are not cached. The results are added to a graph which is then
    returned.

    Args:
        terms_and_dtypes (set): A list of tuples where each tuple contains a term and its data type.
        repo (Repo): An instance of the Repo class.
        system_repo (Repo): An instance of the Repo class with the Prez system graph.

    Returns:
        annotations_g (Graph): A graph containing the processed terms and their data types.
    """
    annotations_g = Graph()
    cache = caches.get("default")  # This always returns the SAME instance
    results = await cache.multi_get(list(terms_and_dtypes))
    zipped = list(zip(terms_and_dtypes, results))

    cached = [z for z in zipped if z[1] is not None]
    await add_cached_entries(annotations_g, cached)

    uncached = [z[0] for z in zipped if z[1] is None]
    if uncached:
        await process_uncached_terms(uncached, repo, system_repo, annotations_g)

    return annotations_g


async def add_cached_entries(
    annotations_g: Graph, cached: List[Tuple[URIRef, FrozenSet[Tuple[URIRef, Literal]]]]
):
    """
    This function adds the cached entries to the graph. It iterates over the cached entries and for each entry,
    it extracts the subject and the frozenset of predicate-object pairs. Then, it adds the expanded triple
    (subject, predicate, object) to the graph.

    Args:
        annotations_g (Graph): A graph to which the cached entries are added.
        cached (list): A list of cached entries.

    Returns:
        None
    """
    for triples in cached:
        subject = triples[0]  # Extract the subject from the current cached object
        predicate_objects = triples[
            1
        ]  # Extract the frozenset of predicate-object pairs
        # Iterate over each predicate-object pair in the frozenset
        for pred, obj in predicate_objects:
            # Add the expanded triple (subject, predicate, object) to 'annotations_g'
            annotations_g.add((subject, pred, obj))


async def process_uncached_terms(
    terms: List[URIRef], repo: Repo, system_repo: Repo, annotations_g: Graph
):
    """
    This function processes the terms that are not cached. It sends queries to the annotations repository and the
    main repository to get the results for the uncached terms. The results are then added to the graph and also
    cached for future use.

    Args:
        terms (list): A list of terms that are not cached.
        repo (Repo): An instance of the Repo class.
        annotations_g (Graph): A graph to which the results are added.

    Returns:
        None
    """
    annotations_repo = await get_annotations_repo()
    annotations_query = AnnotationsConstructQuery(
        terms=[IRI(value=term) for term in terms]
    ).to_string()

    context_results = await annotations_repo.send_queries(
        rdf_queries=[annotations_query], tabular_queries=[]
    )
    repo_results = await repo.send_queries(
        rdf_queries=[annotations_query], tabular_queries=[]
    )
    system_results = await system_repo.send_queries(
        rdf_queries=[annotations_query], tabular_queries=[]
    )

    all_results = context_results[0] + repo_results[0] + system_results[0]

    # Initialize subjects_map with each term having an empty set to start with
    subjects_map = {term: set() for term in terms}

    for s, p, o in all_results:
        subjects_map[s].add((p, o))

    # Prepare subjects_list, only converting to frozenset where there are actual results
    subjects_list = [
        (subject, frozenset(po_pairs)) if po_pairs else (subject, frozenset())
        for subject, po_pairs in subjects_map.items()
    ]

    # Cache the results
    cache = caches.get("default")
    await cache.multi_set(subjects_list)

    # Add all results to annotations_g
    annotations_g += all_results


async def get_annotation_properties(
    item_graph: Graph,
    repo: Repo,
    system_repo: Repo,
) -> Graph:
    """
    Gets annotation data used for HTML display.
    This includes the label, description, and provenance, if available.
    Note the following three default predicates are always included. This allows context, i.e. background ontologies,
    which are often diverse in the predicates they use, to be aligned with the default predicates used by Prez. The full
    range of predicates used can be manually included via profiles.
    """
    # get all terms and datatypes for which we want to retrieve annotations
    terms = set(term for term in item_graph.all_nodes() if isinstance(term, URIRef))
    dtypes = set(
        term.datatype
        for term in item_graph.all_nodes()
        if isinstance(term, Literal) and term.datatype
    )
    terms_and_types = terms.union(dtypes)
    if not terms_and_types:
        return Graph()

    annotations_g = await process_terms(terms_and_types, repo, system_repo)
    return annotations_g
