from typing import List
from prez.cache import endpoints_graph_cache
from rdflib import URIRef
from prez.cache import profiles_graph_cache
from prez.models.model_exceptions import URINotFoundException, ClassNotFoundException
from prez.sparql.methods import sparql_query_non_async, sparql_ask_non_async


def get_classes(uris: List[URIRef], endpoint: URIRef = None) -> frozenset[URIRef]:
    """
    if endpoint is specified, only classes that the endpoint can deliver will be returned.
    """
    if len(uris) == 0:
        return frozenset()
    q = f"""
    SELECT ?uri ?class
    {{ ?uri a ?class .
    VALUES ?uri {{ {" ".join(['<'+str(uri)+'>' for uri in uris]) } }}
    }}
    """
    r = sparql_query_non_async(q)
    if endpoint:
        endpoint_classes = endpoints_graph_cache.objects(
            subject=endpoint, predicate=URIRef("https://prez.dev/ont/deliversClasses")
        )
        object_classes_delivered_by_endpoint = []
        for c in r[1]:
            if URIRef(c["class"]["value"]) in endpoint_classes:
                object_classes_delivered_by_endpoint.append(
                    (c["uri"]["value"], c["class"]["value"])
                )
        classes = frozenset(object_classes_delivered_by_endpoint)
    else:
        classes = frozenset([(c["uri"]["value"], c["class"]["value"]) for c in r[1]])
    # add profiles classes
    # profiles_classes = profiles_graph_cache.query(q)
    return classes
