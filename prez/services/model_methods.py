from rdflib import URIRef

from prez.cache import endpoints_graph_cache
from prez.sparql.methods import Repo


async def get_classes(
    uri: URIRef, repo: Repo, endpoint: URIRef = None
) -> frozenset[URIRef]:
    """
    if endpoint is specified, only classes that the endpoint can deliver will be returned.
    """
    q = f"""
    SELECT ?class
    {{ <{uri}> a ?class }}
    """
    _, r = await repo.send_queries([], [(uri, q)])
    tabular_result = r[0]  # should only be one result - only one query sent
    if endpoint != URIRef("https://prez.dev/endpoint/object"):
        endpoint_classes = list(
            endpoints_graph_cache.objects(
                subject=endpoint,
                predicate=URIRef("https://prez.dev/ont/deliversClasses"),
            )
        )
        object_classes_delivered_by_endpoint = []
        for c in tabular_result[1]:
            if URIRef(c["class"]["value"]) in endpoint_classes:
                object_classes_delivered_by_endpoint.append(URIRef(c["class"]["value"]))
        classes = frozenset(object_classes_delivered_by_endpoint)
    else:
        classes = frozenset([c["class"]["value"] for c in tabular_result[1]])
    return classes
