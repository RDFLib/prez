from aiocache import caches
from pyoxigraph.pyoxigraph import Store
from rdflib import ConjunctiveGraph, Graph

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

# These caches live in this process, so a serializer only buys a copy of the value on
# every read and write - pickling and unpickling a set of URIs for every term of every
# response. What they hold is immutable (frozensets of annotations and classes, and
# URIRefs), so the value itself can be handed out.
_IN_MEMORY_CACHE = {
    "cache": "aiocache.SimpleMemoryCache",
    "serializer": {"class": "aiocache.serializers.NullSerializer"},
}

caches.set_config(
    {
        "default": dict(_IN_MEMORY_CACHE),
        "curies": dict(_IN_MEMORY_CACHE),
        "classes": dict(_IN_MEMORY_CACHE),
        "queryables": dict(_IN_MEMORY_CACHE),
    }
)
