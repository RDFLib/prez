from rdflib import Graph, ConjunctiveGraph

tbox_cache = Graph()

profiles_graph_cache = ConjunctiveGraph()
profiles_graph_cache.bind("prez", "https://prez.dev/")

prez_system_graph = Graph()
prez_system_graph.bind("prez", "https://prez.dev/")

prefix_graph = Graph(bind_namespaces="rdflib")

# TODO can probably merge counts graph
counts_graph = Graph()

search_methods = {}
