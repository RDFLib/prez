import copy
import io
import logging
from urllib.parse import urlencode

from fastapi.responses import PlainTextResponse
from rdflib import URIRef, Literal, RDFS
from rdflib.namespace import RDF, Namespace, GEO
from sparql_grammar_pydantic import IRI, Var, TriplesSameSubject, TriplesSameSubjectPath

from prez.cache import endpoints_graph_cache
from prez.config import settings
from prez.models.ogc_features import Collection, Link, Collections
from prez.reference_data.prez_ns import PREZ, ALTREXT, ONT
from prez.renderers.renderer import return_from_graph, return_annotated_rdf
from prez.services.connegp_service import generate_link_headers, RDF_MEDIATYPES
from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri
from prez.services.link_generation import add_prez_links
from prez.services.query_generation.count import CountQuery
from prez.services.query_generation.shacl import NodeShape
from prez.services.query_generation.umbrella import (
    merge_listing_query_grammar_inputs,
    PrezQueryConstructor, )

log = logging.getLogger(__name__)

DWC = Namespace("http://rs.tdwg.org/dwc/terms/")


async def listing_function(
        data_repo,
        system_repo,
        endpoint_nodeshape,
        endpoint_structure,
        search_query,
        concept_hierarchy_query,
        cql_parser,
        pmts,
        profile_nodeshape,
        query_params,
        original_endpoint_type,
):
    if (
            pmts.selected["profile"] == ALTREXT["alt-profile"]
    ):  # recalculate the endpoint node shape
        endpoint_nodeshape = await handle_alt_profile(original_endpoint_type, pmts)

    subselect_kwargs = merge_listing_query_grammar_inputs(
        cql_parser=cql_parser,
        endpoint_nodeshape=endpoint_nodeshape,
        search_query=search_query,
        concept_hierarchy_query=concept_hierarchy_query,
        query_params=query_params,
    )

    # merge subselect and profile triples same subject (for construct triples)
    construct_tss_list = []
    subselect_tss_list = subselect_kwargs.pop("construct_tss_list")
    if subselect_tss_list:
        construct_tss_list.extend(subselect_tss_list)
    if profile_nodeshape.tss_list:
        construct_tss_list.extend(profile_nodeshape.tss_list)

    # add focus node declaration if it's an annotated mediatype
    if "anot+" in pmts.selected["mediatype"]:
        construct_tss_list.append(
            TriplesSameSubject.from_spo(
                subject=profile_nodeshape.focus_node,
                predicate=IRI(value="https://prez.dev/type"),
                object=IRI(value="https://prez.dev/FocusNode"),
            )
        )

    queries = []
    main_query = PrezQueryConstructor(
        construct_tss_list=construct_tss_list,
        profile_triples=profile_nodeshape.tssp_list,
        profile_gpnt=profile_nodeshape.gpnt_list,
        **subselect_kwargs,
    )
    queries.append(main_query.to_string())

    if (
            pmts.requested_mediatypes is not None
            and pmts.requested_mediatypes[0][0] == "application/sparql-query"
    ):
        return PlainTextResponse(queries[0], media_type="application/sparql-query")

    # add a count query if it's an annotated mediatype
    if "anot+" in pmts.selected["mediatype"] and not search_query:
        subselect = copy.deepcopy(main_query.inner_select)
        count_query = CountQuery(original_subselect=subselect).to_string()
        queries.append(count_query)

    # TODO absorb this up the top of function
    if pmts.selected["profile"] == ALTREXT["alt-profile"]:
        query_repo = system_repo
    else:
        query_repo = data_repo

    item_graph, _ = await query_repo.send_queries(queries, [])
    if "anot+" in pmts.selected["mediatype"]:
        await add_prez_links(item_graph, query_repo, endpoint_structure)

    # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
    if search_query:
        count = len(list(item_graph.subjects(RDF.type, PREZ.SearchResult)))
        if count == search_query.limit:
            count_literal = f">{count - 1}"
        else:
            count_literal = f"{count}"
        item_graph.add((PREZ.SearchResult, PREZ["count"], Literal(count_literal)))
    return await return_from_graph(
        item_graph,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        pmts.selected["class"],
        data_repo,
        system_repo,
    )


async def ogc_features_listing_function(
        selected_mediatype,
        url_path,
        collectionId,
        data_repo,
        system_repo,
        cql_parser,
        query_params,
):
    subselect_kwargs = merge_listing_query_grammar_inputs(
        cql_parser=cql_parser,
        query_params=query_params,
    )
    construct_tss_list = []
    subselect_tss_list = subselect_kwargs.pop("construct_tss_list")
    if subselect_tss_list:
        construct_tss_list.extend(subselect_tss_list)
    tssp_list = []
    if not collectionId:  # list Feature Collections
        triple = (Var(value="focus_node"),
                  IRI(value=RDF.type),
                  IRI(value=GEO.FeatureCollection)
                  )
        construct_tss_list.append(TriplesSameSubject.from_spo(*triple))
        tssp_list.append(TriplesSameSubjectPath.from_spo(*triple))
    else:  # list items in a Feature Collection
        parent_curie = collectionId
        parent_uri = await get_uri_for_curie_id(parent_curie)
        triples = [(IRI(value=parent_uri),
                    IRI(value=RDFS.member),
                    Var(value="focus_node")),
                   (IRI(value=parent_uri),
                    IRI(value=RDF.type),
                    IRI(value=GEO.FeatureCollection))
                   ]
        construct_tss_list.extend([TriplesSameSubject.from_spo(*t) for t in triples])
        tssp_list.extend([TriplesSameSubjectPath.from_spo(*t) for t in triples])

    subselect_kwargs["inner_select_tssp_list"].extend(tssp_list)
    query = PrezQueryConstructor(
        construct_tss_list=construct_tss_list,
        profile_triples=tssp_list,
        **subselect_kwargs,
    ).to_string()

    link_headers = generate_link_headers(url_path, selected_mediatype)

    if selected_mediatype == "application/sparql-query":
        content = io.BytesIO(query.encode("utf-8"))
        return content, link_headers

    item_graph, _ = await data_repo.send_queries([query], [])
    annotations_graph = await return_annotated_rdf(item_graph, data_repo, system_repo)

    if selected_mediatype == "application/json":
        collections = create_collections_json(item_graph, annotations_graph, url_path, selected_mediatype)
        content = io.BytesIO(collections.model_dump_json(exclude_none=True).encode("utf-8"))

    # TODO append to geojson once library imported
    else:
        content = io.BytesIO(
            item_graph.serialize(format="turtle", encoding="utf-8")
        )
    return content, link_headers


def create_collections_json(item_graph, annotations_graph, url_path, selected_mediatype):
    collections_list = []
    for s, p, o in item_graph.triples((None, RDF.type, GEO.FeatureCollection)):
        curie_id = get_curie_id_for_uri(s)
        collections_list.append(
            Collection(
                id=curie_id,
                title=annotations_graph.value(subject=s, predicate=PREZ.label, default=None),
                description=annotations_graph.value(subject=s, predicate=PREZ.description, default=None),
                links=[Link(
                    href=URIRef(f"{settings.system_uri}{url_path}/{curie_id}/items?{urlencode({'_mediatype': mt})}"),
                    rel="items", type=mt) for mt in ["application/geo+json", *RDF_MEDIATYPES]]
            )
        )
    collections = Collections(
        collections=collections_list,
        links=[
            Link(
                href=URIRef(f"{settings.system_uri}{url_path}?{urlencode({'_mediatype': mt})}"),
                rel="self" if mt == selected_mediatype else "alternate",
                type=mt,
                title="this document"
            )
            for mt in ["application/json", *RDF_MEDIATYPES]
        ]
    )
    return collections


async def handle_alt_profile(original_endpoint_type, pmts):
    endpoint_nodeshape_map = {
        ONT["ObjectEndpoint"]: URIRef("http://example.org/ns#AltProfilesForObject"),
        ONT["ListingEndpoint"]: URIRef("http://example.org/ns#AltProfilesForListing"),
    }
    endpoint_uri = endpoint_nodeshape_map[original_endpoint_type]
    endpoint_nodeshape = NodeShape(
        uri=endpoint_uri,
        graph=endpoints_graph_cache,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
        path_nodes={
            "path_node_1": IRI(value=pmts.selected["class"])
        },  # hack - not sure how (or if) the class can be
        # 'dynamicaly' expressed in SHACL. The class is only known at runtime
    )
    return endpoint_nodeshape
