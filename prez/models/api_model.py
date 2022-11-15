from rdflib import Namespace, URIRef

from prez.cache import api_info_graph

PREZ = Namespace("https://kurrawong.net/prez/")


def populate_api_info(ENABLED_PREZS, SYSTEM_URI):
    for prez in ENABLED_PREZS:
        api_info_graph.add((URIRef(SYSTEM_URI), PREZ.enabledPrezFlavour, PREZ[prez]))
