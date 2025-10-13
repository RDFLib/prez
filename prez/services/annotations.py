import asyncio
import logging
from typing import FrozenSet, List, Set, Tuple

from aiocache import caches
from oxrdflib._converter import to_ox, from_ox
from pyoxigraph import (
    Store as OxiStore,
    NamedNode as OxiNamedNode,
    Literal as OxiLiteral,
    Quad as OxiQuad,
    DefaultGraph as OxiDefaultGraph,
)
from rdflib import Graph, Literal, URIRef
from sparql_grammar_pydantic import IRI

from prez.dependencies import get_annotations_repo
from prez.repositories import Repo
from prez.services.query_generation.annotations import AnnotationsConstructQuery

log = logging.getLogger(__name__)


async def get_annotations(
    terms_and_dtypes: Set[URIRef], repo: Repo, system_repo: Repo
) -> Graph:
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


async def get_annotations_for_oxigraph(
    terms_and_dtypes: Set[OxiNamedNode], repo: Repo, system_repo: Repo
) -> OxiStore:
    """
    This function processes the terms and their data types. It first retrieves the cached results for the given terms
    and data types. Then, it processes the terms that are not cached. The results are added to a graph which is then
    returned.

    Args:
        terms_and_dtypes (set): A list of tuples where each tuple contains a term and its data type.
        repo (Repo): An instance of the Repo class.
        system_repo (Repo): An instance of the Repo class with the Prez system graph.

    Returns:
        annotations_store (OxiStore): A oxigraph store containing the processed terms and their data types.
    """
    annotations_store = OxiStore()
    oxi_default_graph = OxiDefaultGraph()
    cache = caches.get("default")  # This always returns the SAME instance
    # Cache always uses URIRefs, so we convert OxiNamedNode to URIRef
    results = await cache.multi_get(list(URIRef(t.value) for t in terms_and_dtypes))
    zipped = list(zip(terms_and_dtypes, results))

    cached = [z for z in zipped if z[1] is not None]
    # Add cached entries to the oxigraph store
    subject: OxiNamedNode
    for subject, po_pairs in cached:
        if po_pairs:
            for po_pair in po_pairs:
                if po_pair is not None and len(po_pair) == 2:
                    predicate = to_ox(po_pair[0])
                    object_ = to_ox(po_pair[1])
                    annotations_store.add(
                        OxiQuad(subject, predicate, object_, oxi_default_graph)
                    )

    uncached = [z[0] for z in zipped if z[1] is None]
    if uncached:
        await process_uncached_terms_for_oxigraph(
            uncached, repo, system_repo, annotations_store
        )

    return annotations_store


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
    terms: List[URIRef], data_repo: Repo, system_repo: Repo, annotations_g: Graph
):
    """
    This function processes the terms that are not cached. It sends queries to the annotations repository and the
    main repository to get the results for the uncached terms. The results are then added to the graph and also
    cached for future use.

    Args:
        terms (list): A list of terms that are not cached.
        data_repo (Repo): An instance of the Repo class.
        annotations_g (Graph): A graph to which the results are added.

    Returns:
        None
    """
    annotations_repo = await get_annotations_repo()
    annotations_query = AnnotationsConstructQuery(
        terms=[IRI(value=term) for term in terms]
    ).to_string()
    data_repo_query_task = asyncio.ensure_future(
        data_repo.send_queries(
            rdf_queries=[annotations_query],
            tabular_queries=[],
            return_oxigraph_store=False,
        )
    )
    annotation_repo_query_task = asyncio.ensure_future(
        annotations_repo.send_queries(
            rdf_queries=[annotations_query],
            tabular_queries=[],
            return_oxigraph_store=False,
        )
    )

    system_repo_query_task = asyncio.ensure_future(
        system_repo.send_queries(
            rdf_queries=[annotations_query],
            tabular_queries=[],
            return_oxigraph_store=False,
        )
    )
    await asyncio.sleep(0)  # Yield control to allow the parallel tasks to kick-start
    all_results = Graph()
    # Wait the local ones first, annotation repo and system repo queries
    system_repo_results = await system_repo_query_task
    all_results += system_repo_results[0]
    annotation_repo_results = await annotation_repo_query_task
    all_results += annotation_repo_results[0]
    # now wait for the data repo (might be remote)
    data_repo_results = await data_repo_query_task
    all_results += data_repo_results[0]

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


async def process_uncached_terms_for_oxigraph(
    terms: List[OxiNamedNode],
    data_repo: Repo,
    system_repo: Repo,
    annotations_store: OxiStore,
):
    """
    This function processes the terms that are not cached. It sends queries to the annotations repository and the
    main repository to get the results for the uncached terms. The results are then added to the graph and also
    cached for future use.

    Args:
        terms (list): A list of terms that are not cached.
        data_repo (Repo): An instance of the Repo class.
        annotations_g (Graph): A graph to which the results are added.

    Returns:
        None
    """
    annotations_repo = await get_annotations_repo()
    annotations_query = AnnotationsConstructQuery(
        terms=[IRI(value=term.value) for term in terms]
    ).to_string()
    data_repo_query_task = asyncio.ensure_future(
        data_repo.send_queries(
            rdf_queries=[annotations_query],
            tabular_queries=[],
            return_oxigraph_store=True,
        )
    )
    annotation_repo_query_task = asyncio.ensure_future(
        annotations_repo.send_queries(
            rdf_queries=[annotations_query],
            tabular_queries=[],
            return_oxigraph_store=True,
        )
    )

    system_repo_query_task = asyncio.ensure_future(
        system_repo.send_queries(
            rdf_queries=[annotations_query],
            tabular_queries=[],
            return_oxigraph_store=True,
        )
    )
    await asyncio.sleep(0)  # Yield control to allow the parallel tasks to kick-start

    # Initialize subjects_map with each term having an empty set to start with
    uriref_subjects_map: dict[URIRef, set] = {
        URIRef(term.value): set() for term in terms
    }

    # Wait the local ones first, annotation repo and system repo queries
    system_repo_results = await system_repo_query_task
    system_repo_result_store: OxiStore = system_repo_results[0]
    for quad in system_repo_result_store.quads_for_pattern(None, None, None, None):
        uriref_subjects_map[URIRef(quad[0].value)].add(
            (from_ox(quad[1]), from_ox(quad[2]))
        )
        annotations_store.add(quad)

    annotation_repo_results = await annotation_repo_query_task
    annotation_repo_result_store: OxiStore = annotation_repo_results[0]
    for quad in annotation_repo_result_store.quads_for_pattern(None, None, None, None):
        uriref_subjects_map[URIRef(quad[0].value)].add(
            (from_ox(quad[1]), from_ox(quad[2]))
        )
        annotations_store.add(quad)

    # now wait for the data repo (might be remote)
    data_repo_results = await data_repo_query_task
    data_repo_result_store: OxiStore = data_repo_results[0]
    for quad in data_repo_result_store.quads_for_pattern(None, None, None, None):
        uriref_subjects_map[URIRef(quad[0].value)].add(
            (from_ox(quad[1]), from_ox(quad[2]))
        )
        annotations_store.add(quad)

    # Prepare subjects_list, only converting to frozenset where there are actual results
    subjects_list = [
        (subject, frozenset(po_pairs)) if po_pairs else (subject, frozenset())
        for subject, po_pairs in uriref_subjects_map.items()
    ]

    # Cache the results
    cache = caches.get("default")
    await cache.multi_set(subjects_list)


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
    all_terms = (
        set(item_graph.subjects(unique=True))
        .union(set(item_graph.predicates(unique=True)))
        .union(set(item_graph.objects(unique=True)))
    )
    all_uris = set(term for term in all_terms if isinstance(term, URIRef))
    all_dtypes = set(
        term.datatype
        for term in all_terms
        if isinstance(term, Literal) and term.datatype
    )
    terms_and_types = all_uris.union(all_dtypes)
    if not terms_and_types:
        return Graph()

    annotations_g = await get_annotations(terms_and_types, repo, system_repo)
    return annotations_g


async def get_annotation_properties_for_oxigraph(
    item_store: OxiStore,
    repo: Repo,
    system_repo: Repo,
) -> OxiStore:
    """
    Gets annotation data used for HTML display.
    This includes the label, description, and provenance, if available.
    Note the following three default predicates are always included. This allows context, i.e. background ontologies,
    which are often diverse in the predicates they use, to be aligned with the default predicates used by Prez. The full
    range of predicates used can be manually included via profiles.

    Note, this is the oxigraph version, it finds all terms and datatypes from the item oxigraph store,
    and retrieves annotations for them.
    But the response is still an rdflib Graph, so it can be used in the same way as the rdflib version.
    This is because the annotations cache and all annotations logic are still based on URIRefs and rdflib Graphs.
    """
    # get all terms and datatypes for which we want to retrieve annotations
    all_uris: set[OxiNamedNode] = set()
    all_dtypes: set[OxiNamedNode] = set()
    for quad in item_store:
        if isinstance(quad[0], OxiNamedNode):
            all_uris.add(quad[0])
        elif isinstance(quad[0], OxiLiteral):
            if quad[0].datatype is not None:
                all_dtypes.add(quad[0].datatype)
        if isinstance(quad[1], OxiNamedNode):
            all_uris.add(quad[1])
        elif isinstance(quad[1], OxiLiteral):
            if quad[1].datatype is not None:
                all_dtypes.add(quad[1].datatype)
        if isinstance(quad[2], OxiNamedNode):
            all_uris.add(quad[2])
        elif isinstance(quad[2], OxiLiteral):
            if quad[2].datatype is not None:
                all_dtypes.add(quad[2].datatype)
    if len(all_uris) == 0 and len(all_dtypes) == 0:
        return OxiStore()
    terms_and_types: set[OxiNamedNode] = all_uris.union(all_dtypes)
    annotations_store = await get_annotations_for_oxigraph(
        terms_and_types, repo, system_repo
    )
    return annotations_store
