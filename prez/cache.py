from aiocache import Cache
from pyoxigraph.pyoxigraph import Store
from rdflib import Graph, ConjunctiveGraph, Dataset

from prez.repositories import PyoxigraphRepo

tbox_cache = Graph()
tbox_cache_aio = Cache.MEMORY

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

annotations_store = Store()
annotations_repo = PyoxigraphRepo(annotations_store)

oxrdflib_store = Graph(store="Oxigraph")
