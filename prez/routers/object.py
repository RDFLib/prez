from string import Template
from typing import FrozenSet

from fastapi import APIRouter, Request, HTTPException, status, Query
from rdflib import Graph, Literal, URIRef, PROF, DCTERMS
from starlette.responses import PlainTextResponse

from prez.cache import endpoints_graph_cache, profiles_graph_cache
from prez.models.listing import ListingModel
from prez.models.object_item import ObjectItem
from prez.models.profiles_and_mediatypes import ProfilesMediatypesInfo
from prez.queries.object import object_inbound_query, object_outbound_query
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph, return_profiles
from prez.routers.identifier import get_iri_route
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.model_methods import get_classes
from prez.sparql.methods import send_queries
from prez.sparql.methods import sparql_query_non_async
from prez.sparql.objects_listings import (
    get_endpoint_template_queries,
    generate_relationship_query,
    generate_item_construct,
    generate_listing_construct,
    generate_listing_count_construct,
)

router = APIRouter(tags=["Object"])


@router.get(
    "/count", summary="Get object's statement count", response_class=PlainTextResponse
)
def count_route(
    curie: str,
    inbound: str = Query(
        None,
        examples={
            "skos:inScheme": {
                "summary": "skos:inScheme",
                "value": "http://www.w3.org/2004/02/skos/core#inScheme",
            },
            "skos:topConceptOf": {
                "summary": "skos:topConceptOf",
                "value": "http://www.w3.org/2004/02/skos/core#topConceptOf",
            },
            "empty": {"summary": "Empty", "value": None},
        },
    ),
    outbound: str = Query(
        None,
        examples={
            "empty": {"summary": "Empty", "value": None},
            "skos:hasTopConcept": {
                "summary": "skos:hasTopConcept",
                "value": "http://www.w3.org/2004/02/skos/core#hasTopConcept",
            },
        },
    ),
):
    """Get an Object's statements count based on the inbound or outbound predicate"""
    iri = get_iri_route(curie)

    if inbound is None and outbound is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "At least 'inbound' or 'outbound' is supplied a valid IRI.",
        )

    if inbound and outbound:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only provide one value for either 'inbound' or 'outbound', not both.",
        )

    if inbound is not None:
        query = object_inbound_query(iri, inbound)
        _, rows = sparql_query_non_async(query)
        for row in rows:
            return row["count"]["value"]

    query = object_outbound_query(iri, outbound)
    _, rows = sparql_query_non_async(query)
    for row in rows:
        return row["count"]["value"]


@router.get("/object", summary="Object")
async def object_function(
    request: Request,
):
    object_item = ObjectItem(**request.path_params, **request.query_params)
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=object_item.classes
    )
    # ignore profile returned by ProfilesMediatypesInfo for now - there is no 'hierarchy' among prez flavours' profiles
    # at present, the behaviour for which should be chosen (or if one should be chosen at all) has not been defined.

    # TODO following is probably only needed if mediatype is an annotated mediatype
    object_item.selected_class = None
    # we are interested in all classes and endpoints which can deliver these
    endpoint_to_relations = get_endpoint_info_for_classes(object_item.classes)
    relationship_query = generate_relationship_query(
        object_item.uri, endpoint_to_relations
    )
    item_query = generate_item_construct(object_item, object_item.profile)
    item_graph, tabular_results = await send_queries(
        rdf_queries=[item_query],
        tabular_queries=[(object_item.uri, relationship_query)],
    )
    # construct the system endpoint links
    internal_links_graph = Graph()
    generate_system_links_object(
        internal_links_graph, tabular_results[0][1], object_item.uri
    )
    return await return_from_graph(
        item_graph + internal_links_graph,
        prof_and_mt_info.mediatype,
        PREZ["profile/open"],
        prof_and_mt_info.profile_headers,
    )


async def item_function(request: Request, object_curie: str):
    # TODO pull object item functions out to here and pass results in as params

    # curie -> uri
    # get_classes func

    object_item = ObjectItem(  # object item now does not need request
        object_curie=object_curie,
        **request.path_params,
        **request.query_params,
        endpoint_uri=request.scope["route"].name,
    )
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=object_item.classes
    )
    object_item.selected_class = prof_and_mt_info.selected_class
    object_item.profile = prof_and_mt_info.profile

    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(object_item.selected_class),
            prof_and_mt_info=prof_and_mt_info,
        )

    item_query = generate_item_construct(object_item, object_item.profile)
    item_members_query = generate_listing_construct(
        object_item, prof_and_mt_info.profile, 1, 20
    )
    if object_item.selected_class == URIRef("http://www.w3.org/ns/dx/prof/Profile"):
        item_graph = profiles_graph_cache.query(item_query).graph
        if item_members_query:
            list_graph = profiles_graph_cache.query(item_members_query).graph
            item_graph += list_graph
    else:
        item_graph, _ = await send_queries(rdf_queries=[item_query, item_members_query])
    if "anot+" in prof_and_mt_info.mediatype:
        await _add_prez_links(item_graph)
    return await return_from_graph(
        item_graph,
        prof_and_mt_info.mediatype,
        object_item.profile,
        prof_and_mt_info.profile_headers,
        prof_and_mt_info.selected_class,
    )


async def listing_function(
    request: Request, page: int = 1, per_page: int = 20, uri: str = None
):
    listing_item = ListingModel(
        **request.path_params,
        **request.query_params,
        endpoint_uri=request.scope["route"].name,
        uri=uri,
    )
    prof_and_mt_info = ProfilesMediatypesInfo(
        request=request, classes=listing_item.classes
    )
    listing_item.selected_class = prof_and_mt_info.selected_class
    listing_item.profile = prof_and_mt_info.profile

    if prof_and_mt_info.profile == URIRef(
        "http://www.w3.org/ns/dx/conneg/altr-ext#alt-profile"
    ):
        return await return_profiles(
            classes=frozenset(listing_item.selected_class),
            prof_and_mt_info=prof_and_mt_info,
        )

    item_members_query = generate_listing_construct(
        listing_item, prof_and_mt_info.profile, page=page, per_page=per_page
    )
    count_query = generate_listing_count_construct(listing_item)
    if listing_item.selected_class in [
        URIRef("https://prez.dev/ProfilesList"),
        PROF.Profile,
    ]:
        list_graph = profiles_graph_cache.query(item_members_query).graph
        count_graph = profiles_graph_cache.query(count_query).graph
        item_graph = list_graph + count_graph
    else:
        item_graph, _ = await send_queries(
            rdf_queries=[count_query, item_members_query]
        )
    if "anot+" in prof_and_mt_info.mediatype:
        await _add_prez_links(item_graph)
    return await return_from_graph(
        item_graph,
        prof_and_mt_info.mediatype,
        listing_item.profile,
        prof_and_mt_info.profile_headers,
        prof_and_mt_info.selected_class,
    )


async def _add_prez_links(graph: Graph):
    # get all URIRefs - if Prez can find a class and endpoint for them, an internal link will be generated.
    uris = [uri for uri in graph.all_nodes() if isinstance(uri, URIRef)]
    classes_for_uris = get_classes(uris)
    ep_queries = []
    for uri, klass in classes_for_uris:
        endpoint_to_relations = get_endpoint_info_for_classes(frozenset([klass]))
        relationship_query = generate_relationship_query(uri, endpoint_to_relations)
        if relationship_query:
            ep_queries.append((uri, relationship_query))
    _, tabular_results = await send_queries([], ep_queries)
    internal_links_graph = Graph()
    for uri, result in tabular_results:
        generate_system_links_object(internal_links_graph, result, uri)
    graph.__iadd__(internal_links_graph)


def get_endpoint_info_for_classes(classes: FrozenSet[URIRef]) -> dict:
    """
    Queries Prez's in memory reference data for endpoints to determine which endpoints are relevant for the classes an
    object has, along with information about "parent" objects included in the URL path for the object. This information
    is whether the relationship in RDF is expected to be from the parent to the child, or from the child to the parent,
    and the predicate used for the relationship.
    """
    endpoint_query = get_endpoint_template_queries(classes)
    results = endpoints_graph_cache.query(endpoint_query)
    endpoint_to_relations = {}
    if results.bindings != [{}]:
        for result in results.bindings:
            endpoint_template = result["endpointTemplate"]
            relation = result["relation"]
            direction = result["direction"]
            if endpoint_template not in endpoint_to_relations:
                endpoint_to_relations[endpoint_template] = [(relation, direction)]
            else:
                endpoint_to_relations[endpoint_template].append((relation, direction))
    return endpoint_to_relations


def generate_system_links_object(
    internal_links_graph: Graph, relationship_results: list, object_uri: str
):
    """
    Generates system links for objects from the 'object' endpoint
    relationship_results: a list of dictionaries, one per endpoint, each dictionary contains:
    1. an endpoint template with parameters denoted by `$` to be populated using python's string Template library
    2. the arguments to populate this endpoint template, as URIs. The get_curie_id_for_uri function is used to convert
    these to curies.
    """
    endpoints = []
    for endpoint_results in relationship_results:
        endpoint_template = Template(endpoint_results["endpoint"]["value"])
        template_args = {
            k: get_curie_id_for_uri(v["value"])
            for k, v in endpoint_results.items()
            if k != "endpoint"
        } | {"object": get_curie_id_for_uri(object_uri)}
        endpoints.append(endpoint_template.substitute(template_args))
    for endpoint in endpoints:
        internal_links_graph.add(
            (
                URIRef(object_uri),
                PREZ["link"],
                Literal(endpoint),
            )
        )
    # TODO include the actual relationships between the object and the parent objects in the graph
    for ep_result in relationship_results:
        for k, v in ep_result.items():
            if k != "endpoint":
                uri = URIRef(v["value"])
                curie = get_curie_id_for_uri(uri)
                internal_links_graph.add(
                    (
                        uri,
                        DCTERMS.identifier,
                        Literal(curie, datatype=PREZ.identifier),
                    )
                )


# def generate_system_links_non_object(
#         endpoint_to_relations: dict,
#         object_curie: str,
#         parent_1_curie: str = None,
#         parent_2_curie: str = None,
# ) -> Graph:
#     """
#     Generates system links for objects from other than the 'object' endpoint.
#     """
#     endpoint_template = Template(next(iter(endpoint_to_relations)))
#     template_args = {
#         "object": object_curie,
#         "parent_1": parent_1_curie,
#         "parent_2": parent_2_curie,
#     }
#     endpoint = endpoint_template.substitute(template_args)
#
#     internal_links_graph = Graph()
#     endpoints = []
#     for endpoint_results in relationship_results:
#         endpoint_template = Template(endpoint_results["endpoint"]["value"])
#         template_args = {
#                             k: get_curie_id_for_uri(v["value"])
#                             for k, v in endpoint_results.items()
#                             if k != "endpoint"
#                         } | {"object": get_curie_id_for_uri(object_uri)}
#         endpoints.append(endpoint_template.substitute(template_args))
#     for endpoint in endpoints:
#         internal_links_graph.add(
#             (
#                 URIRef(object_uri),
#                 PREZ["link"],
#                 Literal(endpoint),
#             )
#         )
#     return internal_links_graph
