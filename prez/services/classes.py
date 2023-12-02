from aiocache import caches
from rdflib import URIRef

from prez.repositories import Repo
from prez.services.query_generation.classes import ClassesSelectQuery
from temp.grammar import IRI


async def get_classes_single(uri: URIRef, repo: Repo):
    results = await get_classes([uri], repo)
    return results.get(uri, set())


async def get_classes(uris: list[URIRef], repo: Repo):
    """
    This function gets the classes for a given URI

    Args:
        uris (set): A set of uris to get classes for.
        repo (Repo): An instance of the Repo class.

    Returns:
        klasses (dict): A dict of URIs and their klasses.
    """
    klasses = {}
    cache = caches.get("classes")  # This always returns the SAME instance
    results = await cache.multi_get(uris)
    zipped = list(zip(uris, results))

    cached = [z for z in zipped if z[1] is not None]
    await add_cached_entries(klasses, cached)

    uncached = [z[0] for z in zipped if z[1] is None]
    if uncached:
        klasses = await process_uncached_classes(uncached, repo, klasses)

    return klasses


async def add_cached_entries(
    klasses: dict, cached: list[tuple[URIRef, frozenset[URIRef]]]
):
    """
    This function adds the cached entries to the dict
    """
    for tuples in cached:
        subject = tuples[0]  # Extract the subject from the current cached object
        placeholder = list(tuples[1])  # Extract the frozenset of predicate-object pairs
        # Iterate over each predicate-object pair in the frozenset
        for obj in placeholder:
            # Add the expanded triple (subject, predicate, object) to 'annotations_g'
            if not klasses.get(subject):
                klasses[subject] = set()
            klasses[subject].add(obj)


async def process_uncached_classes(uris: list[URIRef], data_repo: Repo, klasses: dict):
    """
    This function gets classes for uris where there is no current cache entry.

    Args:
        uris (list): A list of uris that are not cached.
        data_repo (Repo): An instance of the Repo class.
        klasses (dict): A dict to which the results are added.

    Returns:
        None
    """
    klasses_query = ClassesSelectQuery(
        uris=[IRI(value=uri) for uri in uris]
    ).to_string()

    repo_results = await data_repo.send_queries(
        rdf_queries=[], tabular_queries=[(None, klasses_query)]
    )

    # Initialize subjects_map with each term having an empty set to start with
    subjects_map = {uri: set() for uri in uris}

    for result in repo_results[1][0][1]:
        klass = result["class"]["value"]
        uri = result["uri"]["value"]
        subjects_map[URIRef(uri)].add(URIRef(klass))

    # Prepare subjects_list, only converting to frozenset where there are actual results
    subjects_list = [
        (subject, set(klasses)) if klasses else (subject, set())
        for subject, klasses in subjects_map.items()
    ]

    # Cache the results
    cache = caches.get("classes")
    await cache.multi_set(subjects_list)

    return klasses | subjects_map
