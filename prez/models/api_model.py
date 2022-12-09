from rdflib import Namespace, URIRef, DCTERMS, RDF, XSD

from prez.cache import prez_system_graph
from prez.services.sparql_new import (
    construct_main_classes_and_context_graphs,
    construct_instances_without_context_graph,
    top_level_updates,
)
from prez.services.sparql_utils import sparql_construct

PREZ = Namespace("https://prez.dev/")


async def populate_api_info(settings):
    for prez in settings.enabled_prezs:
        prez_system_graph.add(
            (URIRef(settings.system_uri), PREZ.enabledPrezFlavour, PREZ[prez])
        )
        # top_classes_and_context_g = await get_top_class_instances_and_context_graphs(TOP_LEVEL_CLASSES[prez], prez)
        # prez_system_graph.__iadd__(top_classes_and_context_g)
        # select instances which do not have context graphs, log these instances
        if settings.generate_context:
            inplace_updated_query = top_level_updates(
                settings.top_level_classes[prez], settings.collection_classes[prez]
            )
            response = await sparql_construct(inplace_updated_query, prez)
            print("")


# display a message that as the X environment variable is set, context graphs will be generated for these instances


async def get_top_class_instances_and_context_graphs(top_level_classes, prez):
    query = construct_main_classes_and_context_graphs(top_level_classes)
    results = await sparql_construct(query, prez)
    return results[1]

    # query = construct_instances_without_context_graph()
    # classes_without_context = top_classes_and_context_g.query(query).graph
    # class_categories = set(top_classes_and_context_g.objects(predicate=DCTERMS.type))
    # for top_level_class in class_categories:
    #     # existing_identifiers =
    # ids = top_classes_and_context_g.objects(None, DCTERMS.identifier)
    # existing_slugs = [id for id in ids if id.datatype == PREZ.slug]
    # existing_ids = [id for id in ids if id.datatype == PREZ.slug]
    # instance_uris = [result["instance"] for result in results.bindings]
    # return instance_uris


# async def generate_identifiers():
#     for prez in ENABLED_PREZS:
