from prez.sparql.methods import sparql_query_non_async


def get_classes(uri, prez):
    q = f"""
    SELECT ?class
    {{<{uri}> a ?class . }}
    """
    r = sparql_query_non_async(q, prez)
    return frozenset([c["class"]["value"] for c in r[1]])
