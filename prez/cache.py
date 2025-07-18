from aiocache import caches
from pyoxigraph.pyoxigraph import Store
from rdflib import ConjunctiveGraph, Dataset, Graph

profiles_graph_cache = Graph()
profiles_graph_cache.bind("prez", "https://prez.dev/")

endpoints_graph_cache = ConjunctiveGraph()
endpoints_graph_cache.bind("prez", "https://prez.dev/")

prez_system_graph = Graph()
prez_system_graph.bind("prez", "https://prez.dev/")

prefix_graph = Graph(bind_namespaces="none")

# TODO can probably merge counts graph
counts_graph = Graph()

links_ids_graph_cache = Store()

store = Store()

persistent_store = None

system_store = Store()

annotations_store = Store()

queryable_props = {}

oxrdflib_store = Graph(store="Oxigraph")

caches.set_config(
    {
        "default": {
            "cache": "aiocache.SimpleMemoryCache",
            "serializer": {"class": "aiocache.serializers.PickleSerializer"},
        },
        "curies": {
            "cache": "aiocache.SimpleMemoryCache",
            "serializer": {"class": "aiocache.serializers.PickleSerializer"},
        },
        "classes": {
            "cache": "aiocache.SimpleMemoryCache",
            "serializer": {"class": "aiocache.serializers.PickleSerializer"},
        },
    }
)
