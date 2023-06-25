from typing import List
from prez.cache import endpoints_graph_cache
from rdflib import URIRef

from prez.models.model_exceptions import URINotFoundException, ClassNotFoundException
from prez.sparql.methods import sparql_query_non_async, sparql_ask_non_async


def get_classes(uri: URIRef, endpoint: URIRef = None) -> frozenset[URIRef]:
    q = f"""
    SELECT ?class
    {{<{uri}> a ?class . }}
    """
    r = sparql_query_non_async(q)
    if endpoint:
        endpoint_classes = endpoints_graph_cache.objects(
            subject=endpoint, predicate=URIRef("https://prez.dev/ont/deliversClasses")
        )
        object_classes_delivered_by_endpoint = []
        for c in r[1]:
            if URIRef(c["class"]["value"]) in endpoint_classes:
                object_classes_delivered_by_endpoint.append(c["class"]["value"])
        classes = frozenset(object_classes_delivered_by_endpoint)
    else:
        classes = frozenset([c["class"]["value"] for c in r[1]])
    if not classes:
        #  does the URI exist?
        r = sparql_ask_non_async(f"ASK {{<{uri}> ?p ?o}}")
        if not r[1]:  # uri not found
            raise URINotFoundException(uri)
        else:  # we found the URI but it has no classes
            raise ClassNotFoundException(uri)
    return classes
