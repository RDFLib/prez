def support_graph_exists():
    """Check if the support graph exists in the triplestore."""
    from app import settings

    for endpoint in settings.sparql_creds:
        query = f"""
        ASK {{
            GRAPH <{settings.support_graph}> {{
                ?s ?p ?o
            }}
        }}
        """
        result = sparql_construct(query, endpoint)
        if result[0]:
            return True

    return results["boolean"]
