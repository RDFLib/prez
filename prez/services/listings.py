import copy
import io
import json
import logging
from urllib.parse import urlencode

from fastapi.responses import PlainTextResponse
from rdf2geojson import convert
from rdflib import URIRef, Literal
from rdflib.namespace import RDF, Namespace, GEO
from sparql_grammar_pydantic import IRI, Var, TriplesSameSubject, TriplesSameSubjectPath, PrimaryExpression, \
    GraphPatternNotTriples, Bind, Expression, IRIOrFunction, OptionalGraphPattern, GroupGraphPattern, \
    GroupGraphPatternSub, TriplesBlock

from prez.cache import endpoints_graph_cache
from prez.config import settings
from prez.models.ogc_features import Collection, Link, Collections
from prez.models.query_params import NON_ANOT_RDF_MEDIA_TYPES
from prez.reference_data.prez_ns import PREZ, ALTREXT, ONT, OGCFEAT
from prez.renderers.renderer import return_from_graph, return_annotated_rdf
from prez.services.connegp_service import RDF_MEDIATYPES, generate_link_headers
from prez.services.curie_functions import get_uri_for_curie_id, get_curie_id_for_uri
from prez.services.generate_queryables import generate_queryables_json
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
        endpoint_uri_type,
        endpoint_nodeshape,
        profile_nodeshape,
        selected_mediatype,
        url_path,
        data_repo,
        system_repo,
        cql_parser,
        query_params,
        **path_params,
):
    collectionId = path_params.get("collectionId")
    subselect_kwargs = merge_listing_query_grammar_inputs(
        endpoint_nodeshape=endpoint_nodeshape,
        cql_parser=cql_parser,
        query_params=query_params,
    )
    # merge subselect and profile triples same subject (for construct triples)
    construct_tss_list = []
    subselect_tss_list = subselect_kwargs.pop("construct_tss_list")
    if subselect_tss_list:
        construct_tss_list.extend(subselect_tss_list)
    if profile_nodeshape.tss_list:
        construct_tss_list.extend(profile_nodeshape.tss_list)

    queries = []
    if endpoint_uri_type[0] in [OGCFEAT["queryables-local"], OGCFEAT["queryables-global"]]:
        queryable_var = Var(value="queryable")
        innser_select_triple = (Var(value="focus_node"), queryable_var, Var(value="queryable_value"))
        subselect_kwargs["inner_select_tssp_list"].append(TriplesSameSubjectPath.from_spo(*innser_select_triple))
        subselect_kwargs["inner_select_vars"] = [queryable_var]
        construct_triple = (
            queryable_var, IRI(value=RDF.type), IRI(value="http://www.opengis.net/def/rel/ogc/1.0/Queryable"))
        construct_tss_list = [TriplesSameSubject.from_spo(*construct_triple)]
        query = PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            **subselect_kwargs,
        ).to_string()
        queries.append(query)
    elif not collectionId:  # list Feature Collections
        query = PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            **subselect_kwargs,
        ).to_string()
        queries.append(query)
    else:  # list items in a Feature Collection
        # add inbound links - not currently possible via profiles
        opt_inbound_gpnt = _add_inbound_triple_pattern_match(construct_tss_list)
        profile_nodeshape.gpnt_list.append(opt_inbound_gpnt)

        feature_list_query = PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            profile_gpnt=profile_nodeshape.gpnt_list,
            **subselect_kwargs,
        ).to_string()
        queries.append(feature_list_query)

        collection_uri = await get_uri_for_curie_id(collectionId)
        # Features listing requires CBD of the Feature Collection as well; reuse items profile to get all props/bns to
        # depth two.
        gpnt = GraphPatternNotTriples(
            content=Bind(
                expression=Expression.from_primary_expression(
                    PrimaryExpression(
                        content=IRIOrFunction(iri=IRI(value=collection_uri))
                    )
                ),
                var=Var(value="focus_node"),
            )
        )
        feature_collection_query = PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            profile_gpnt=profile_nodeshape.gpnt_list,
            inner_select_gpnt=[gpnt],  # BIND(<fc_uri> AS ?focus_node)
            limit=1,
            offset=0,
        ).to_string()
        queries.append(feature_collection_query)

    # link_headers = generate_link_headers(links)
    link_headers = None

    if selected_mediatype == "application/sparql-query":
        # queries_dict = {f"query_{i}": query for i, query in enumerate(queries)}
        # just do the first query for now:
        content = io.BytesIO(queries[0].encode("utf-8"))
        # content = io.BytesIO(json.dumps(queries_dict).encode("utf-8"))
        return content, link_headers

    item_graph, _ = await data_repo.send_queries(queries, [])
    annotations_graph = await return_annotated_rdf(item_graph, data_repo, system_repo)

    if selected_mediatype == "application/json":
        if endpoint_uri_type[0] in [OGCFEAT["queryables-local"], OGCFEAT["queryables-global"]]:
            queryables = generate_queryables_json(item_graph, annotations_graph, url_path, endpoint_uri_type[0])
            content = io.BytesIO(queryables.model_dump_json(exclude_none=True, by_alias=True).encode("utf-8"))
        else:
            collections = create_collections_json(item_graph, annotations_graph, url_path, selected_mediatype)
            all_links = collections.links
            for coll in collections.collections:
                all_links.extend(coll.links)
            link_headers = generate_link_headers(all_links)
            content = io.BytesIO(collections.model_dump_json(exclude_none=True).encode("utf-8"))

    elif selected_mediatype == "application/geo+json":
        geojson = convert(g=item_graph, do_validate=False, iri2id=get_curie_id_for_uri)
        content = io.BytesIO(json.dumps(geojson).encode("utf-8"))
    elif selected_mediatype in NON_ANOT_RDF_MEDIA_TYPES:
        content = io.BytesIO(
            item_graph.serialize(format=selected_mediatype, encoding="utf-8")
        )
    return content, link_headers


def _add_inbound_triple_pattern_match(construct_tss_list):
    triple = (Var(value="inbound_s"), Var(value="inbound_p"), Var(value="focus_node"))
    construct_tss_list.append(TriplesSameSubject.from_spo(*triple))
    inbound_tssp_list = [TriplesSameSubjectPath.from_spo(*triple)]
    opt_inbound_gpnt = GraphPatternNotTriples(
        content=OptionalGraphPattern(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    triples_block=TriplesBlock.from_tssp_list(inbound_tssp_list)
                )
            )
        )
    )
    return opt_inbound_gpnt


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
