import httpx
from rdflib import Graph, URIRef, RDFS, Literal, DCTERMS
from pathlib import Path

if Path("tbox_cache.nt").exists():
    tbox_cache = Graph().parse("tbox_cache.nt", format="nt")
else:
    tbox_cache = Graph()

profiles_graph_cache = Graph()

api_info_graph = Graph()
