from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, ConjunctiveGraph, Dataset

tbox_cache = Graph()

profiles_graph_cache = ConjunctiveGraph()
profiles_graph_cache.bind("prez", "https://prez.dev/")

endpoints_graph_cache = ConjunctiveGraph()
endpoints_graph_cache.bind("prez", "https://prez.dev/")

prez_system_graph = Graph()
prez_system_graph.bind("prez", "https://prez.dev/")

prefix_graph = Graph(bind_namespaces="rdflib")

# TODO can probably merge counts graph
counts_graph = Graph()

links_ids_graph_cache = Dataset()
links_ids_graph_cache.bind("prez", "https://prez.dev/")

search_methods = {}

store = Store()

system_store = Store()

oxrdflib_store = Graph(store="Oxigraph")
