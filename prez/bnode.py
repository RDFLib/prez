from rdflib import Graph, URIRef, BNode
from rdflib.term import Node


def dfs(node: Node, graph: Graph, depth: int = 0):
    """
    Perform a depth-first search of the blank node max depth of the resource recursively.

    :param node: An RDFLib Node.
    :param graph: The resource's concise bounded description graph.
    :param depth: The current depth count.
    """
    # Base case
    if not isinstance(node, BNode):
        return depth

    # Recursive case
    max_depth = depth
    for obj in graph.objects(node, None):
        max_depth = max(max_depth, dfs(obj, graph, depth + 1))

    return max_depth


def get_bnode_depth(node: URIRef, graph: Graph) -> int:
    """Get the max blank node depth of the node in the graph.

    :param node: The starting resource node.
    :param graph: The resource's concise bounded description graph.

    >>> graph = Graph().parse("example-data.ttl")
    >>> resource = URIRef("node-name")
    >>> cbd = graph.cbd(resource)
    >>> depth = get_bnode_depth(resource, cbd)
    """
    max_depth = 0
    for obj in graph.objects(node, None):
        if isinstance(obj, BNode):
            max_depth = max(max_depth, dfs(obj, graph))

    return max_depth
