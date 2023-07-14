from rdflib import Graph, URIRef, BNode


def get_bnode_depth(
    graph: Graph, node: URIRef | BNode = None, depth: int = 0, seen: list[BNode] = None
) -> int:
    """Get the max blank node depth of the node in the graph.

    This is a recursive function.

    >>> graph = Graph().parse(...)
    >>> depth = get_bnode_depth(graph, URIRef("node-name"))
    """
    if seen is None:
        seen = []

    if isinstance(node, BNode) or depth == 0:
        for o in graph.objects(node, None):
            if isinstance(o, BNode) and o not in seen:
                seen.append(o)
                depth = get_bnode_depth(graph, o, depth + 1, seen)

    return depth
