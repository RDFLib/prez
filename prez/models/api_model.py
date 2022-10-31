from rdflib import Graph, Namespace, URIRef

from app import settings

SYSTEM_URI = settings.SYSTEM_URI
ENABLED_PREZS = settings.ENABLED_PREZS.split("|")

PREZ = Namespace("https://kurrawong.net/prez/")

api_info_graph = Graph()


def populate_api_info():
    for prez in ENABLED_PREZS:
        api_info_graph.add((URIRef(SYSTEM_URI), PREZ.enabledPrezFlavour, PREZ[prez]))
