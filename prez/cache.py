from pathlib import Path

from rdflib import Graph, ConjunctiveGraph

if Path("tbox_cache.nt").exists():
    tbox_cache = Graph().parse("tbox_cache.nt", format="nt")
else:
    tbox_cache = Graph()

profiles_graph_cache = ConjunctiveGraph()
profiles_graph_cache.bind("prez", "https://prez.dev/")
prez_system_graph = Graph()
prez_system_graph.bind("prez", "https://prez.dev/")

# TODO can probably merge counts graph
counts_graph = Graph()

search_methods = {}
