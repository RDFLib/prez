import asyncio
import copy
import io
import json
import logging

from fastapi.responses import PlainTextResponse
from oxrdflib._converter import to_ox
from pyoxigraph import (
    RdfFormat,
    Store as OxiStore,
    Quad as OxiQuad,
    NamedNode as OxiNamedNode,
    BlankNode as OxiBlankNode,
    Literal as OxiLiteral,
    DefaultGraph as OxiDefaultGraph,
)
from rdf2geojson import convert
from rdflib import Literal, Namespace
from rdflib.namespace import GEO, RDF, PROF
from sparql_grammar_pydantic import (
    IRI,
    TriplesSameSubject,
    Var,
    SelectClause,
    WhereClause,
    GroupGraphPattern,
    GroupGraphPatternSub,
    TriplesBlock,
    TriplesSameSubjectPath,
    SolutionModifier,
    SubSelect,
    LimitOffsetClauses,
    LimitClause,
    OffsetClause,
)

from prez.cache import prefix_graph
from prez.config import settings
from prez.enums import NonAnnotatedRDFMediaType, AnnotatedRDFMediaType
from prez.reference_data.prez_ns import ALTREXT, OGCFEAT, PREZ
from prez.renderers.renderer import (
    return_annotated_rdf_for_oxigraph,
    return_from_graph,
    generate_geojson_extras,
    handle_alt_profile,
    generate_queryables_from_shacl_definition,
    create_collections_json,
    generate_link_headers,
    get_geojson_int_count,
)
from prez.repositories import Repo
from prez.services.connegp_service import OXIGRAPH_SERIALIZER_TYPES_MAP
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.generate_queryables import generate_queryables_json
from prez.services.link_generation import add_prez_links_for_oxigraph
from prez.services.query_generation.count import CountQuery
from prez.services.query_generation.facet import FacetQuery
from prez.services.query_generation.umbrella import (
    PrezQueryConstructor,
    merge_listing_query_grammar_inputs,
)

log = logging.getLogger(__name__)

DWC = Namespace("http://rs.tdwg.org/dwc/terms/")


async def extract_queryables_rdf(system_repo: Repo):
    """
    Extract queryables RDF from the system store using a DESCRIBE query.
    Returns an Oxigraph store containing all queryables and their property shapes.
    """
    describe_query = "DESCRIBE ?queryable WHERE { ?queryable a <http://www.opengis.net/doc/IS/cql2/1.0/Queryable> }"
    queryables_store, _ = await system_repo.send_queries(
        [describe_query], [], return_oxigraph_store=True
    )
    return queryables_store


async def listing_profiles(
    data_repo,
    system_repo,
    query_params,
    pmts,
):
    """
    Optimized listing function specifically for profiles.
    Uses DESCRIBE for data fetching and a separate query for counting.
    """
    limit = query_params.limit
    offset = limit * (int(query_params.page) - 1)

    # Query to get the profiles within the limit/offset using DESCRIBE on selected nodes
    describe_query_template = """
        DESCRIBE ?focus_node
        WHERE {{
            {{
                SELECT DISTINCT ?focus_node
                WHERE {{
                    ?focus_node a <{profile_class}> .
                }}
                LIMIT {limit} OFFSET {offset}
            }}
        }}
    """
    describe_query = describe_query_template.format(
        profile_class=PROF.Profile, limit=limit, offset=offset
    )

    count_query_template = """
        CONSTRUCT {{ [] <https://prez.dev/count> ?count }}
        {{
            SELECT (COUNT(DISTINCT ?profile) as ?count)
            WHERE {{
                ?profile a <{profile_class}> .
            }}
        }}
    """
    count_query = count_query_template.format(profile_class=PROF.Profile)
    profiles_g, _ = await system_repo.send_queries([describe_query, count_query], [])
    for profile_uri in profiles_g.subjects(predicate=RDF.type, object=PROF.Profile):
        profiles_g.add((profile_uri, RDF.type, PREZ.FocusNode))
        curie = get_curie_id_for_uri(profile_uri)
        profiles_g.add((profile_uri, PREZ.link, Literal(f"/profiles/{curie}")))

    response = await return_from_graph(
        profiles_g,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        PROF.Profile,
        data_repo,
        system_repo,
        query_params,
    )
    return response


def _add_geom_triple_pattern_match(tssp_list: list[TriplesSameSubjectPath]):
    triples = [
        (Var(value="focus_node"), IRI(value=GEO.hasGeometry), Var(value="bn")),
        (Var(value="bn"), IRI(value=GEO.asWKT), Var(value="wkt")),
    ]
    tssp_list.extend([TriplesSameSubjectPath.from_spo(*triple) for triple in triples])


async def listing_function(
    data_repo: Repo,
    system_repo: Repo,
    endpoint_nodeshape,
    endpoint_structure,
    search_query,
    concept_hierarchy_query,
    cql_parser,
    pmts,
    profile_nodeshape,
    query_params,
    original_endpoint_type,
    url,
):
    if (
        pmts.selected["profile"] == ALTREXT["alt-profile"]
    ):  # recalculate the endpoint node shape
        endpoint_nodeshape = await handle_alt_profile(original_endpoint_type, pmts)
        # set the query repo
        query_repo: Repo = system_repo
    else:
        query_repo = data_repo

    subselect_kwargs = merge_listing_query_grammar_inputs(
        cql_parser=cql_parser,
        endpoint_nodeshape=endpoint_nodeshape,
        search_query=search_query,
        concept_hierarchy_query=concept_hierarchy_query,
        query_params=query_params,
    )
    return_geojson = pmts.selected["mediatype"] == "application/geo+json"
    if return_geojson:
        # Ensure the focus nodes have a geometry in the SPARQL
        # subselect. If they are missing, the subsequent GeoJSON conversion will drop any Features without geometries.
        _add_geom_triple_pattern_match(subselect_kwargs["inner_select_tssp_list"])

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

    hits_response = query_params.result_type == "hits"
    main_query = PrezQueryConstructor(
        construct_tss_list=construct_tss_list,
        profile_triples=profile_nodeshape.tssp_list,
        profile_gpnt=profile_nodeshape.gpnt_list,
        **subselect_kwargs,
    )
    queries: list[str] = []
    # add faceting query if requested
    facet_profile_uri = None
    facets_query = None
    if query_params.facet_profile:
        # Check if main query has a subselect, if not, create one with the `?focus_node a ?type` triple
        # This will allow the count query below to reuse the subselect preventing an error.
        if not hasattr(main_query, "inner_select") or main_query.inner_select is None:
            # Create the ?focus_node a ?type triple
            basic_triple = TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value="http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                object=Var(value="type"),
            )

            # Create a new subselect with this triple
            basic_subselect = SubSelect(
                select_clause=SelectClause(
                    variables_or_all=[Var(value="focus_node")],
                    distinct=True,
                ),
                where_clause=WhereClause(
                    group_graph_pattern=GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            triples_block=TriplesBlock.from_tssp_list([basic_triple])
                        )
                    )
                ),
                solution_modifier=SolutionModifier(
                    limit_offset=LimitOffsetClauses(
                        limit_clause=LimitClause(limit=settings.listing_count_limit),
                        offset_clause=OffsetClause(offset=0),
                    )
                ),
            )

            # Add the subselect to the main query's where clause
            from sparql_grammar_pydantic import (
                GraphPatternNotTriples,
                GroupOrUnionGraphPattern,
            )

            subselect_gpnt = GraphPatternNotTriples(
                content=GroupOrUnionGraphPattern(
                    group_graph_patterns=[GroupGraphPattern(content=basic_subselect)]
                )
            )

            # Insert the subselect at the beginning of the where clause
            if hasattr(
                main_query.where_clause.group_graph_pattern.content,
                "graph_patterns_or_triples_blocks",
            ):
                main_query.where_clause.group_graph_pattern.content.graph_patterns_or_triples_blocks.insert(
                    0, subselect_gpnt
                )

        facet_profile_uri, facets_query = await FacetQuery.create_facets_query(
            main_query, query_params
        )

    if not hits_response:
        queries.append(main_query.to_string())
    if facets_query:
        queries.append(facets_query.to_string())
    count_query: str | None = None
    # add a count query if it's an annotated mediatype or counted search
    if (
        ("anot+" in pmts.selected["mediatype"] and not search_query)
        or (return_geojson and "human" in profile_nodeshape.uri.lower())
        or (search_query and settings.search_uses_listing_count_limit)
    ):
        # When returning GeoJSON, only include
        # the numberMatched count if it's a hits request
        include_count_query: bool = (not return_geojson) or hits_response
        if include_count_query:
            subselect = copy.deepcopy(main_query.inner_select)
            count_query = CountQuery(original_subselect=subselect).to_string()

    if (
        pmts.requested_mediatypes is not None
        and pmts.requested_mediatypes[0][0] == "application/sparql-query"
    ):
        if len(queries) == 0 and count_query is not None:
            resp_bytes: bytes = count_query.encode("utf-8")
        elif len(queries) > 0:
            resp_bytes = queries[0].encode("utf-8")
        else:
            resp_bytes = b"No Queries Generated"
        return PlainTextResponse(resp_bytes, media_type="application/sparql-query")

    if count_query is not None:
        # add the count query to the list, so it can be sent in parallel
        queries.append(count_query)

    item_store: OxiStore
    if len(queries) > 0:
        item_store, _ = await query_repo.send_queries(
            queries, [], return_oxigraph_store=True
        )
    else:
        # Dummy empty store, if there are no queries to run
        item_store = OxiStore()
    default = OxiDefaultGraph()
    if facet_profile_uri:
        item_store.add(
            OxiQuad(
                OxiBlankNode(),
                OxiNamedNode(PREZ.facetProfile),
                OxiNamedNode(facet_profile_uri),
                default,
            )
        )
    if "anot+" in pmts.selected["mediatype"]:
        item_store.add(
            OxiQuad(
                OxiBlankNode(),
                OxiNamedNode(PREZ.currentProfile),
                OxiNamedNode(pmts.selected["profile"]),
                default,
            )
        )
        await add_prez_links_for_oxigraph(item_store, query_repo, endpoint_structure)

    # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
    if search_query and not settings.search_uses_listing_count_limit:
        count = len(
            list(
                item_store.quads_for_pattern(
                    None, OxiNamedNode(RDF.type), OxiNamedNode(PREZ.SearchResult), None
                )
            )
        )
        if count == search_query.limit:
            count_literal = f">{(count - 1) * query_params.page}"
        else:
            # last page, this is the actual count = (complete pages) * limit + count
            count_literal = f"{(query_params.limit * (query_params.page - 1)) + count}"
        item_store.add(
            OxiQuad(
                OxiNamedNode(PREZ.SearchResult),
                OxiNamedNode(PREZ["count"]),
                OxiLiteral(count_literal),
                default,
            )
        )
    return await return_from_graph(
        item_store,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        pmts.selected["class"],
        data_repo,
        system_repo,
        query_params,
        url,
    )


async def ogc_features_listing_function(
    endpoint_uri_type,
    endpoint_nodeshape,
    profile_nodeshape,
    selected_mediatype,
    url,
    data_repo: Repo,
    system_repo: Repo,
    cql_parser,
    query_params,
    path_params,
):
    count_query = None
    collection_uri = path_params.get("collection_uri")
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

    return_geojson = selected_mediatype == "application/geo+json"
    queries = []
    queryables = None
    if endpoint_uri_type[0] in [
        OGCFEAT["queryables-local"],
        OGCFEAT["queryables-global"],
    ]:
        queryables = await generate_queryables_from_shacl_definition(
            url, endpoint_uri_type[0], system_repo
        )
        if queryables:  # from shacl definitions
            content = io.BytesIO(
                queryables.model_dump_json(
                    exclude_none=True,
                    by_alias=True,
                ).encode("utf-8")
            )
        else:
            queryable_var = Var(value="queryable")
            innser_select_triple = (
                Var(value="focus_node"),
                queryable_var,
                Var(value="queryable_value"),
            )
            subselect_kwargs["inner_select_tssp_list"].append(
                TriplesSameSubjectPath.from_spo(*innser_select_triple)
            )
            subselect_kwargs["inner_select_vars"] = [queryable_var]
            subselect_kwargs["limit"] = settings.listing_count_limit
            construct_triple = (
                queryable_var,
                IRI(value=RDF.type),
                IRI(value="http://www.opengis.net/def/rel/ogc/1.0/Queryable"),
            )
            construct_tss_list = [TriplesSameSubject.from_spo(*construct_triple)]
            query = PrezQueryConstructor(
                construct_tss_list=construct_tss_list,
                profile_triples=profile_nodeshape.tssp_list,
                **subselect_kwargs,
            ).to_string()
            queries.append(query)
    elif not collection_uri:  # list Feature Collections
        # Due to the way the mediatype negotiation works,
        # This can never be a GeoJSON response, so
        # does this need to always get the count?
        query = PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            profile_gpnt=profile_nodeshape.gpnt_list,
            **subselect_kwargs,
        )
        queries.append(query.to_string())
        # add the count query
        subselect = copy.deepcopy(query.inner_select)
        count_query = CountQuery(original_subselect=subselect).to_string()
    else:  # list items in a Feature Collection
        feature_list_query = PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            profile_gpnt=profile_nodeshape.gpnt_list,
            **subselect_kwargs,
        )
        hits_response = query_params.result_type == "hits"
        if not hits_response:
            # Add the main features query if it's not a count-only request
            queries.append(feature_list_query.to_string())
        # When returning GeoJSON, only include
        # the numberMatched count if it's a hits request
        include_count_query: bool = (not return_geojson) or hits_response
        if include_count_query:
            # add the count query
            subselect = copy.deepcopy(feature_list_query.inner_select)
            count_query = CountQuery(original_subselect=subselect).to_string()
    link_headers = None
    if selected_mediatype == "application/sparql-query":
        # For a hits query, the queries list might be empty
        if len(queries) == 0 and count_query is not None:
            content = io.BytesIO(count_query.encode("utf-8"))
        elif len(queries) > 0:
            # just show the first query
            content = io.BytesIO(queries[0].encode("utf-8"))
        else:
            # Return a placeholder
            content = io.BytesIO(b"No Queries Generated")
        return content, link_headers

    item_store: OxiStore | None
    if len(queries) == 0:
        # No main query.
        main_query_task = None
    else:
        main_query_task = asyncio.ensure_future(
            data_repo.send_queries(queries, [], return_oxigraph_store=True)
        )
    if count_query:
        # send this in parallel to the main query
        count_query_task = asyncio.ensure_future(
            data_repo.send_queries([count_query], [], return_oxigraph_store=True)
        )
    else:
        count_query_task = None
    if main_query_task is not None or count_query_task is not None:
        await asyncio.sleep(0)  # Yield control to allow the parallel tasks to start
    if main_query_task is not None:
        item_store, _ = await main_query_task
    else:
        # No store, we can only return known metadata
        item_store = None
    matched_count: int | None = None
    if count_query_task is not None:
        count_store: OxiStore
        count_store, _ = await count_query_task
        if count_store is not None:
            # Assuming this response returns only a single triple,
            # and we extract just the object node from that triple
            for q in count_store.quads_for_pattern(None, None, None, None):
                # This could be an int literal, or a string like ">10000"
                # So always convert to str first, then process to an int
                count_str = str(q[2].value)
                matched_count = get_geojson_int_count(count_str)
                break
            else:
                matched_count = 0

    # only need the annotations for mediatypes of application/json or annotated mediatypes
    annotations_store: OxiStore | None = None
    if (
        (selected_mediatype in AnnotatedRDFMediaType)
        or (selected_mediatype == "application/json")
        or (return_geojson and "human" in profile_nodeshape.uri.lower())
    ):
        if item_store is None:
            # No item store, so no annotations possible
            annotations_store = None
        else:
            # This still returns an RDFlib graph of anotations,
            # even when the store is an Oxigraph Store.
            annotations_store = await return_annotated_rdf_for_oxigraph(
                item_store, data_repo, system_repo
            )

    # Handle queryables RDF responses
    if endpoint_uri_type[0] in [
        OGCFEAT["queryables-local"],
        OGCFEAT["queryables-global"],
    ] and (
        selected_mediatype in NonAnnotatedRDFMediaType
        or selected_mediatype in AnnotatedRDFMediaType
    ):
        # Extract queryables RDF from the system store using DESCRIBE query
        queryables_store = await extract_queryables_rdf(system_repo)

        # Handle annotated vs non-annotated RDF
        if selected_mediatype in AnnotatedRDFMediaType:
            serialization_format = selected_mediatype.replace("anot+", "")
            # Get specific annotations for the queryables data (not the entire annotations store)
            specific_annotations_store = await return_annotated_rdf_for_oxigraph(
                queryables_store, data_repo, system_repo
            )
            queryables_store.bulk_extend(specific_annotations_store)
        else:
            serialization_format = selected_mediatype

        # Get the Oxigraph serializer format
        serializer_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(
            serialization_format, RdfFormat.N_TRIPLES
        )

        # Get prefixes for serialization
        oxigraph_prefixes = {
            p: str(n) for p, n in prefix_graph.namespace_manager.namespaces()
        }

        content = io.BytesIO()
        queryables_store.dump(
            content,
            serializer_format,
            from_graph=OxiDefaultGraph(),
            prefixes=oxigraph_prefixes,
        )
        content.seek(0)
        return content, link_headers

    if selected_mediatype == "application/json":
        if endpoint_uri_type[0] in [
            OGCFEAT["queryables-local"],
            OGCFEAT["queryables-global"],
        ]:
            if queryables:  # queryables were generated from SHACL
                pass
            elif item_store is not None and annotations_store is not None:
                # generate them from the data
                queryables = generate_queryables_json(
                    item_store, annotations_store, url, endpoint_uri_type[0]
                )
            if queryables:
                content_bytes = queryables.model_dump_json(
                    exclude_none=True, by_alias=True
                ).encode("utf-8")
            else:
                content_bytes = b"{}"
            content = io.BytesIO(content_bytes)
        else:
            collections = create_collections_json(
                item_store,
                annotations_store,
                url,
                selected_mediatype,
                query_params,
                matched_count,
            )
            all_links = collections.links
            # all_links is used to generate link headers - to minimise the size, only use first 10 feature collections.
            # this is allowed in the spec: https://docs.ogc.org/is/17-069r4/17-069r4.html#_link_headers
            for coll in collections.collections[:10]:
                all_links.extend(coll.links)
            link_headers = generate_link_headers(all_links)
            content = io.BytesIO(
                collections.model_dump_json(exclude_none=True).encode("utf-8")
            )

    elif return_geojson:
        if "human" in profile_nodeshape.uri.lower():  # human readable profile
            kind = "human"
        else:
            kind = "machine"
        if item_store is not None and annotations_store is not None:
            # Add the annotations to the store
            item_store.bulk_extend(annotations_store)
        if item_store is not None:
            geojson = convert(
                g=item_store,
                do_validate=False,
                iri2id=get_curie_id_for_uri,
                kind=kind,
                fc_uri=collection_uri,
                namespace_manager=prefix_graph.namespace_manager,
            )
        else:
            # Dummy empty FeatureCollection for adding metadata
            geojson = {"type": "FeatureCollection", "features": []}
        is_first_page = subselect_kwargs["offset"] == 0
        per_page = subselect_kwargs["limit"]
        link_headers, geojson = await generate_geojson_extras(
            matched_count,
            geojson,
            query_params,
            selected_mediatype,
            url,
            is_first_page,
            per_page,
        )
        content = io.BytesIO(json.dumps(geojson).encode("utf-8"))
    elif selected_mediatype in NonAnnotatedRDFMediaType:
        serializer_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(
            str(selected_mediatype), RdfFormat.N_TRIPLES
        )
        oxigraph_prefixes = {
            p: str(n) for p, n in prefix_graph.namespace_manager.namespaces()
        }
        if item_store is None:
            # Item store could be None, if no queries were generated
            dump_store = OxiStore()
        else:
            dump_store = item_store
        content = io.BytesIO()
        # TODO, what happens if the store has content in a named graph? This can only dump the default graph.
        dump_store.dump(
            content,
            serializer_format,
            from_graph=OxiDefaultGraph(),
            prefixes=oxigraph_prefixes,
        )
        content.seek(0)  # Reset the stream position to the beginning

    elif selected_mediatype in AnnotatedRDFMediaType:
        non_anot_mt = selected_mediatype.replace("anot+", "")
        default = OxiDefaultGraph()
        if item_store is None:
            # Item store could be None, if no queries were generated
            item_store = OxiStore()
        if annotations_store is not None:
            # Add the annotations to the store
            item_store.bulk_extend(annotations_store)
        serializer_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(
            str(non_anot_mt), RdfFormat.N_TRIPLES
        )
        oxigraph_prefixes = {
            p: str(n) for p, n in prefix_graph.namespace_manager.namespaces()
        }
        content = io.BytesIO()
        # TODO, what happens if the store has content in a named graph? This can only dump the default graph.
        item_store.dump(
            content, serializer_format, from_graph=default, prefixes=oxigraph_prefixes
        )
        content.seek(0)  # Reset the stream position to the beginning
    return content, link_headers
