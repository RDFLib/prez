import asyncio
import logging
import os
import time
from itertools import chain
from typing import List, FrozenSet
from aiocache.serializers import PickleSerializer
from aiocache import cached
from rdflib import Graph, URIRef, Literal, Dataset
from rdflib.namespace import RDFS

from prez.cache import tbox_cache, tbox_cache_aio
from prez.config import settings
from prez.dependencies import get_annotations_repo
from prez.reference_data.prez_ns import PREZ
from prez.repositories import Repo
from prez.services.query_generation.annotations import AnnotationsConstructQuery
from temp.grammar import *

log = logging.getLogger(__name__)

pred = IRI(value=URIRef("https://prez.dev/label"))


async def process_terms(terms, repo) -> Graph:
    """
    """
    results = await asyncio.gather(*[process_term(term, repo) for term in terms])
    triples = list(chain(*results))
    annotations_g = Graph()
    for triple in triples:
        annotations_g.add(triple)
    return annotations_g


def term_based_key_builder(func, *args, **kwargs):
    return args[0]


@cached(cache=tbox_cache_aio, key_builder=term_based_key_builder, serializer=PickleSerializer())
async def process_term(term, repo) -> FrozenSet[Tuple[URIRef, URIRef, Literal]]:
    """
    gets annotations for an individual term
    """
    log.info(f"Processing term within func {term}")
    annotations_repo = await get_annotations_repo()
    annotations_query = AnnotationsConstructQuery(
        term=IRI(value=term),
        construct_predicate=IRI(value=PREZ.label),  # TODO change to predicate map
        select_predicates=[IRI(value=RDFS.label)]
    ).to_string()
    # check the prez cache
    context_results = await annotations_repo.send_queries(rdf_queries=[annotations_query], tabular_queries=[])
    # if not found, query the data repo
    repo_results = await repo.send_queries(rdf_queries=[annotations_query], tabular_queries=[])
    all_results = context_results[0] + repo_results[0]
    cacheable_results = frozenset(all_results)
    log.info(f"Processed term {term}, found {len(cacheable_results)} annotations.")
    return cacheable_results


async def get_annotation_properties(
        item_graph: Graph,
        repo: Repo,
) -> Graph:
    """
    Gets annotation data used for HTML display.
    This includes the label, description, and provenance, if available.
    Note the following three default predicates are always included. This allows context, i.e. background ontologies,
    which are often diverse in the predicates they use, to be aligned with the default predicates used by Prez. The full
    range of predicates used can be manually included via profiles.
    """
    terms = set(term for term in item_graph.all_nodes() if isinstance(term, URIRef))
    if not terms:
        return Graph()

    annotations_g = await process_terms(terms, repo)
    return annotations_g
