from typing import List

from rdflib import URIRef

from prez.models.model_exceptions import URINotFoundException, ClassNotFoundException
from prez.sparql.methods import sparql_query_non_async, sparql_ask_non_async


def get_classes(uri: URIRef, parent_predicates: List[URIRef] = None):
    q = f"""
    SELECT ?class
    {{<{uri}> a ?class . }}
    """
    r = sparql_query_non_async(q)
    classes = frozenset([c["class"]["value"] for c in r[1]])
    if not classes:
        #  does the URI exist?
        r = sparql_ask_non_async(f"ASK {{<{uri}> ?p ?o}}")
        if not r[1]:  # uri not found
            raise URINotFoundException(uri)
        else:  # we found the URI but it has no classes (line 14)
            raise ClassNotFoundException(uri)
    return frozenset([c["class"]["value"] for c in r[1]])
