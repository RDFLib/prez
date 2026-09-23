import asyncio
import copy
import hashlib
import io
import json
import time

from aiocache import caches
from fastapi.responses import PlainTextResponse
from pyoxigraph import BlankNode as OxiBlankNode
from pyoxigraph import DefaultGraph as OxiDefaultGraph
from pyoxigraph import Literal as OxiLiteral
from pyoxigraph import NamedNode as OxiNamedNode
from pyoxigraph import Quad as OxiQuad
from pyoxigraph import RdfFormat
from pyoxigraph import Store as OxiStore
from rdf2geojson import convert
from rdflib import Literal, Namespace
from rdflib.namespace import GEO, PROF, RDF, RDFS, XSD
from sparql_grammar import (
    IRI,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitOffsetClauses,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)

from prez.cache import prefix_graph
from prez.config import settings
from prez.dependencies import DummySearchMarker
from prez.enums import AnnotatedRDFMediaType, NonAnnotatedRDFMediaType
from prez.reference_data.prez_ns import ALTREXT, OGCFEAT, PREZ
from prez.renderers.renderer import (
    create_collections_json,
    generate_geojson_extras,
    generate_link_headers,
    generate_queryables_from_shacl_definition,
    get_geojson_int_count,
    handle_alt_profile,
    return_annotated_rdf_for_oxigraph,
    return_from_graph,
)
from prez.repositories import Repo
from prez.services.connegp_service import OXIGRAPH_SERIALIZER_TYPES_MAP
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.generate_queryables import generate_queryables_json
from prez.services.link_generation import add_prez_links_for_oxigraph
from prez.services.prez_logging import get_logger
from prez.services.query_generation.count import CountQuery
from prez.services.query_generation.facet import (
    FacetQuery,
    extract_lucene_facets_from_profile,
    get_facet_profile_uri_from_qsa,
)
from prez.services.query_generation.search_jena_lucene import SearchQueryJenaLucene
from prez.services.query_generation.umbrella import (
    PrezQueryConstructor,
    merge_listing_query_grammar_inputs,
)

log = get_logger(__name__)

DWC = Namespace("http://rs.tdwg.org/dwc/terms/")


def _suppress_nan_lucene_weights(item_store: OxiStore) -> None:
    weight_pred = OxiNamedNode(PREZ.searchResultWeight)
    nan_datatypes = {str(XSD.float), str(XSD.double)}
    to_remove = []
    for quad in item_store.quads_for_pattern(None, weight_pred, None, None):
        obj = quad.object
        if (
            isinstance(obj, OxiLiteral)
            and obj.value == "NaN"
            and obj.datatype is not None
            and obj.datatype.value in nan_datatypes
        ):
            to_remove.append(quad)
    for quad in to_remove:
        item_store.remove(quad)


async def warm_queryables_cache(data_repo: Repo, system_repo: Repo) -> None:
    """
    Pre-warm the queryables cache at startup for performance.
    Generates and caches gzipped queryables for common RDF mediatypes.
    """

    mediatypes_to_warm = [
        "text/anot+turtle",  # Most common annotated format
        "text/turtle",  # Most common non-annotated format
    ]

    for mediatype in mediatypes_to_warm:
        log.info(
            "Warming queryables cache",
            extra={
                "event.name": "queryables.cache.warm.start",
                "http.response.header.content-type": mediatype,
            },
        )
        t0 = time.perf_counter()
        try:
            await handle_queryables_rdf_response(
                endpoint_uri=str(OGCFEAT["queryables-global"]),
                collection_uri=None,
                selected_mediatype=mediatype,
                data_repo=data_repo,
                system_repo=system_repo,
                accept_encoding="gzip",  # Pre-compress for cache
            )
            t1 = time.perf_counter()
            log.info(
                "Queryables cache warmed",
                extra={
                    "event.name": "queryables.cache.warm.complete",
                    "http.response.header.content-type": mediatype,
                    "duration_ms": (t1 - t0) * 1000,
                },
            )
        except Exception:
            log.warning(
                "Failed to warm queryables cache",
                extra={
                    "event.name": "queryables.cache.warm.error",
                    "http.response.header.content-type": mediatype,
                },
                exc_info=True,
            )


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


async def handle_queryables_rdf_response(
    endpoint_uri: str,
    collection_uri: str | None,
    selected_mediatype: str,
    data_repo: Repo,
    system_repo: Repo,
    accept_encoding: str | None = None,
) -> tuple[io.BytesIO, dict | None] | None:
    """
    Handle queryables RDF responses with caching.

    Returns (content, headers) if this is a queryables RDF request.
    Returns None if this is not a queryables RDF request (caller should continue normal flow).

    If the client supports gzip (via Accept-Encoding header), returns pre-gzipped cached bytes.
    Otherwise, falls back to non-cached serialization for compatibility.
    """
    import gzip

    # Only handle RDF mediatypes for queryables
    if not (
        selected_mediatype in NonAnnotatedRDFMediaType
        or selected_mediatype in AnnotatedRDFMediaType
    ):
        return None

    # Check if client supports gzip
    supports_gzip = accept_encoding and "gzip" in accept_encoding.lower()

    if supports_gzip:
        # Check cache for gzipped content
        t0 = time.perf_counter()
        queryables_cache = caches.get("queryables")
        cache_key = f"{endpoint_uri}:{collection_uri}:{selected_mediatype}"
        cached_content = await queryables_cache.get(cache_key)
        t1 = time.perf_counter()
        log.debug(
            "Queryables cache lookup completed",
            extra={
                "event.name": "queryables.cache.lookup",
                "cache_lookup_duration_ms": (t1 - t0) * 1000,
                "http.response.header.content-type": selected_mediatype,
            },
        )

        if cached_content is not None:
            log.debug(
                "Queryables cache hit",
                extra={
                    "event.name": "queryables.cache.hit",
                    "prez.cache.result": "hit",
                    "http.response.header.content-type": selected_mediatype,
                    "response_size_bytes": len(cached_content),
                },
            )
            return io.BytesIO(cached_content), {"Content-Encoding": "gzip"}
    else:
        log.debug(
            "Queryables cache skipped because gzip was not accepted",
            extra={
                "event.name": "queryables.cache.skip",
                "prez.cache.result": "skip",
                "prez.cache.skip_reason": "gzip_not_accepted",
                "http.response.header.content-type": selected_mediatype,
            },
        )

    # Cache miss - do the expensive work
    log.debug(
        "Queryables cache miss",
        extra={
            "event.name": "queryables.cache.miss",
            "prez.cache.result": "miss",
            "http.response.header.content-type": selected_mediatype,
        },
    )

    # Extract queryables RDF from the system store
    t0 = time.perf_counter()
    queryables_store = await extract_queryables_rdf(system_repo)
    t1 = time.perf_counter()
    log.debug(
        "Queryables RDF extracted",
        extra={
            "event.name": "queryables.extract.complete",
            "extraction_duration_ms": (t1 - t0) * 1000,
            "prez.rdf.quad_count": len(queryables_store),
        },
    )

    # Handle annotated vs non-annotated RDF
    if selected_mediatype in AnnotatedRDFMediaType:
        serialization_format = selected_mediatype.replace("anot+", "")
        t2 = time.perf_counter()
        specific_annotations_store = await return_annotated_rdf_for_oxigraph(
            queryables_store, data_repo, system_repo
        )
        queryables_store.bulk_extend(specific_annotations_store)
        t3 = time.perf_counter()
        log.debug(
            "Queryables annotations completed",
            extra={
                "event.name": "queryables.annotations.complete",
                "annotation_duration_ms": (t3 - t2) * 1000,
                "prez.annotation.quad_count": len(specific_annotations_store),
            },
        )
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

    t4 = time.perf_counter()
    content = io.BytesIO()
    queryables_store.dump(
        content,
        serializer_format,
        from_graph=OxiDefaultGraph(),
        prefixes=oxigraph_prefixes,
    )
    content.seek(0)
    t5 = time.perf_counter()
    log.debug(
        "Queryables RDF serialized",
        extra={
            "event.name": "queryables.serialization.complete",
            "serialization_duration_ms": (t5 - t4) * 1000,
            "http.response.header.content-type": selected_mediatype,
        },
    )

    # If client supports gzip, compress, cache, and return gzipped
    if supports_gzip:
        t6 = time.perf_counter()
        raw_bytes = content.getvalue()
        gzipped_bytes = gzip.compress(raw_bytes)
        t7 = time.perf_counter()
        log.debug(
            "Queryables response compressed",
            extra={
                "event.name": "queryables.compression.complete",
                "compression_duration_ms": (t7 - t6) * 1000,
                "input_size_bytes": len(raw_bytes),
                "output_size_bytes": len(gzipped_bytes),
                "compression_ratio_percent": (
                    len(gzipped_bytes) / len(raw_bytes) * 100
                ),
            },
        )

        # Cache the gzipped bytes
        queryables_cache = caches.get("queryables")
        cache_key = f"{endpoint_uri}:{collection_uri}:{selected_mediatype}"
        await queryables_cache.set(cache_key, gzipped_bytes)

        return io.BytesIO(gzipped_bytes), {"Content-Encoding": "gzip"}
    else:
        # Return raw content without caching for non-gzip clients
        return content, None


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
    extra_rdf_queries: list[str] | None = None,
):
    total_start = time.perf_counter()
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
                profile_nodeshape.focus_node,
                IRI(value="https://prez.dev/type"),
                IRI(value="https://prez.dev/FocusNode"),
            )
        )

    hits_response = query_params.result_type == "hits"
    # Resolve Lucene facets from facet_profile before building the main query,
    # so that SearchQueryJenaLucene.has_facets is true when we construct the combined query.
    lucene_facet_profile_uri = None
    if (
        query_params.facet_profile
        and isinstance(search_query, SearchQueryJenaLucene)
        and not search_query.has_facets
    ):
        profile_uri = await get_facet_profile_uri_from_qsa(query_params.facet_profile)
        if profile_uri:
            lucene_facets = extract_lucene_facets_from_profile(profile_uri)
            if lucene_facets is not None:
                search_query.set_facets(lucene_facets)
                lucene_facet_profile_uri = profile_uri

    queries = []
    main_query = None
    if isinstance(search_query, SearchQueryJenaLucene) and search_query.has_facets:
        main_query = search_query.build_combined_query(
            construct_tss_list=construct_tss_list + search_query.facet_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            profile_gpnt=profile_nodeshape.gpnt_list,
        )
        main_query_str = main_query.to_string()
    else:
        main_query = PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_nodeshape.tssp_list,
            profile_gpnt=profile_nodeshape.gpnt_list,
            **subselect_kwargs,
        )
        main_query_str = main_query.to_string()
    # add faceting query if requested
    facets_query = None
    facet_profile_uri = lucene_facet_profile_uri
    if query_params.facet_profile and not lucene_facet_profile_uri:
        # Non-Lucene path: build a SPARQL-based facet query from the profile's sh:property paths
        # Check if main query has a subselect, if not, create one with the `?focus_node a ?type` triple
        # This will allow the count query below to reuse the subselect preventing an error.
        if not hasattr(main_query, "inner_select") or main_query.inner_select is None:
            # Create the ?focus_node a ?type triple
            basic_triple = TriplesSameSubjectPath.from_spo(
                Var(value="focus_node"),
                IRI(value="http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                Var(value="type"),
            )

            # Create a new subselect with this triple
            basic_subselect = SubSelect(
                select_clause=SelectClause.create(
                    Var(value="focus_node"), distinct=True
                ),
                where_clause=WhereClause(
                    GroupGraphPattern(
                        GroupGraphPatternSub([TriplesBlock([basic_triple])])
                    )
                ),
                solution_modifier=SolutionModifier(
                    limit_offset=LimitOffsetClauses.create(
                        limit=settings.listing_count_limit, offset=0
                    )
                ),
            )

            # Add the subselect to the main query's where clause
            subselect_gpnt = GroupOrUnionGraphPattern(
                [GroupGraphPattern(basic_subselect)]
            )

            # Insert the subselect at the beginning of the where clause
            main_query.where_clause.group_graph_pattern.content.add_pattern(
                subselect_gpnt, prepend=True
            )

        facet_profile_uri, facets_query = await FacetQuery.create_facets_query(
            main_query, query_params
        )

    # A hits request asks only for the count, so the main query is not run for it.
    if not hits_response:
        queries.append(main_query_str)
        if extra_rdf_queries:
            queries.extend(query for query in extra_rdf_queries if query)

    if facets_query:
        queries.append(facets_query.to_string())
    count_query: str | None = None
    # add a count query if it's an annotated mediatype or counted search OR if it's a hits request
    if (
        ("anot+" in pmts.selected["mediatype"] and not search_query)
        or (return_geojson and "human" in profile_nodeshape.uri.lower())
        or (
            search_query
            and not isinstance(search_query, SearchQueryJenaLucene)
            and settings.search_uses_listing_count_limit
        )
        or hits_response  # a hits request is a request for the count itself
    ):
        # When LISTING_COUNT_ON_DEMAND is enabled, apply conditional logic similar to OGC features
        if settings.listing_count_on_demand:
            # Only include count query when:
            # - It's a GeoJSON response AND it's a hits request, OR
            # - It's NOT a GeoJSON response and it's a hits request
            include_count_query: bool = hits_response
        else:
            # Original behavior: when returning GeoJSON, only include the count if it's a hits request
            include_count_query: bool = (not return_geojson) or hits_response
        if include_count_query:
            subselect = copy.deepcopy(main_query.inner_select)
            count_query = CountQuery(original_subselect=subselect).to_string()

    if (
        pmts.requested_mediatypes is not None
        and pmts.requested_mediatypes[0][0] == "application/sparql-query"
    ):
        # Every query the request would send, in the order it would send them. A hits
        # request has only the count, so that is what comes back as query 1.
        to_send = queries + ([count_query] if count_query is not None else [])
        if not to_send:
            return PlainTextResponse(
                "No Queries Generated", media_type="application/sparql-query"
            )
        return PlainTextResponse(
            "\n\n".join(
                f"# Query {index}\n{query}"
                for index, query in enumerate(to_send, start=1)
            ),
            media_type="application/sparql-query",
        )

    if count_query is not None:
        # add the count query to the list, so it can be sent in parallel
        queries.append(count_query)

    query_start_time = time.perf_counter()
    item_store: OxiStore
    if len(queries) > 0:
        item_store, _ = await query_repo.send_queries(
            queries, [], return_oxigraph_store=True
        )
    else:
        # Dummy empty store, if there are no queries to run
        item_store = OxiStore()
    log.debug(
        "Listing query completed",
        extra={
            "event.name": "listing.query.complete",
            "query_duration_ms": (time.perf_counter() - query_start_time) * 1000,
            "prez.query.count": len(queries),
            "http.response.header.content-type": pmts.selected["mediatype"],
            "prez.profile": str(pmts.selected["profile"]),
            "prez.rdf.quad_count": len(item_store),
        },
    )
    if isinstance(search_query, SearchQueryJenaLucene):
        _suppress_nan_lucene_weights(item_store)
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
        link_generation_start = time.perf_counter()
        log.debug(
            "Starting Prez link generation for listing response",
            extra={
                "event.name": "listing.link_generation.start",
                "prez.rdf.quad_count": len(item_store),
                "http.response.header.content-type": pmts.selected["mediatype"],
            },
        )
        await add_prez_links_for_oxigraph(item_store, query_repo, endpoint_structure)
        log.debug(
            "Listing link generation completed",
            extra={
                "event.name": "listing.link_generation.complete",
                "link_generation_duration_ms": (
                    time.perf_counter() - link_generation_start
                )
                * 1000,
                "http.response.header.content-type": pmts.selected["mediatype"],
                "prez.profile": str(pmts.selected["profile"]),
                "prez.rdf.quad_count": len(item_store),
            },
        )

        # Inject dummy search results for non-text search requests
        if isinstance(search_query, DummySearchMarker):
            # Extract all focus nodes from the result store
            focus_node_quads = list(
                item_store.quads_for_pattern(
                    None, OxiNamedNode(PREZ["type"]), OxiNamedNode(PREZ.FocusNode), None
                )
            )

            # Create a dummy search result for each focus node
            for focus_node_quad in focus_node_quads:
                # focus_node_quad.subject is already an OxiNamedNode
                focus_node = focus_node_quad.subject
                focus_node_uri = (
                    focus_node.value
                )  # Get the URI string without angle brackets

                # Create a unique hash ID for this dummy search result
                hash_input = f"{focus_node_uri}:dummy"
                hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()
                dummy_search_result_uri = f"urn:hash:{hash_digest}"

                # Add dummy search result quads
                item_store.add(
                    OxiQuad(
                        OxiNamedNode(dummy_search_result_uri),
                        OxiNamedNode(RDF.type),
                        OxiNamedNode(PREZ.SearchResult),
                        default,
                    )
                )
                item_store.add(
                    OxiQuad(
                        OxiNamedNode(dummy_search_result_uri),
                        OxiNamedNode(PREZ.searchResultURI),
                        focus_node,  # Use the OxiNamedNode directly
                        default,
                    )
                )
                item_store.add(
                    OxiQuad(
                        OxiNamedNode(dummy_search_result_uri),
                        OxiNamedNode(PREZ.searchResultMatch),
                        OxiLiteral(""),
                        default,
                    )
                )
                item_store.add(
                    OxiQuad(
                        OxiNamedNode(dummy_search_result_uri),
                        OxiNamedNode(PREZ.searchResultPredicate),
                        OxiNamedNode(RDFS.label),
                        default,
                    )
                )
                item_store.add(
                    OxiQuad(
                        OxiNamedNode(dummy_search_result_uri),
                        OxiNamedNode(PREZ.searchResultWeight),
                        OxiLiteral("0"),
                        default,
                    )
                )

    # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
    if (
        search_query
        and not isinstance(search_query, (DummySearchMarker, SearchQueryJenaLucene))
        and not settings.search_uses_listing_count_limit
    ):
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
    elif isinstance(search_query, DummySearchMarker):
        # For dummy search results, count them and add the count
        count = len(
            list(
                item_store.quads_for_pattern(
                    None, OxiNamedNode(RDF.type), OxiNamedNode(PREZ.SearchResult), None
                )
            )
        )
        item_store.add(
            OxiQuad(
                OxiNamedNode(PREZ.SearchResult),
                OxiNamedNode(PREZ["count"]),
                OxiLiteral(str(count)),
                default,
            )
        )
    render_start = time.perf_counter()
    response = await return_from_graph(
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
    render_ms = (time.perf_counter() - render_start) * 1000
    total_ms = (time.perf_counter() - total_start) * 1000
    log.debug(
        "Listing response completed",
        extra={
            "event.name": "listing.function.complete",
            "http.response.header.content-type": pmts.selected["mediatype"],
            "prez.profile": str(pmts.selected["profile"]),
            "prez.query.count": len(queries),
            "prez.rdf.quad_count": len(item_store),
            "render_duration_ms": render_ms,
            "duration_ms": total_ms,
        },
    )
    return response


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
    accept_encoding: str | None = None,
):
    total_start = time.perf_counter()
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
    build_start = time.perf_counter()
    if endpoint_uri_type[0] in [
        OGCFEAT["queryables-local"],
        OGCFEAT["queryables-global"],
    ]:
        # Handle queryables RDF responses with caching (returns early if cached or RDF mediatype)
        queryables_result = await handle_queryables_rdf_response(
            endpoint_uri=endpoint_uri_type[0],
            collection_uri=collection_uri,
            selected_mediatype=selected_mediatype,
            data_repo=data_repo,
            system_repo=system_repo,
            accept_encoding=accept_encoding,
        )
        if queryables_result is not None:
            return queryables_result

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
    build_ms = (time.perf_counter() - build_start) * 1000
    log.debug(
        "OGC listing queries built",
        extra={
            "event.name": "ogc_listing.built",
            "http.response.header.content-type": selected_mediatype,
            "prez.profile": (
                str(profile_nodeshape.uri)
                if getattr(profile_nodeshape, "uri", None) is not None
                else None
            ),
            "prez.collection.uri": str(collection_uri) if collection_uri else None,
            "prez.query.count": len(queries),
            "prez.query.has_count_query": bool(count_query),
            "build_duration_ms": build_ms,
        },
    )
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
    main_query_start = time.perf_counter()
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
    log.debug(
        "OGC listing main query completed",
        extra={
            "event.name": "ogc_listing.main_query.complete",
            "http.response.header.content-type": selected_mediatype,
            "prez.rdf.quad_count": (len(item_store) if item_store is not None else 0),
            "operation_duration_ms": (time.perf_counter() - main_query_start) * 1000,
        },
    )
    matched_count: int | None = None
    if count_query_task is not None:
        count_store: OxiStore
        count_await_start = time.perf_counter()
        count_store, _ = await count_query_task
        count_await_ms = (time.perf_counter() - count_await_start) * 1000
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
        log.debug(
            "OGC listing count query completed",
            extra={
                "event.name": "ogc_listing.count_query.complete",
                "http.response.header.content-type": selected_mediatype,
                "prez.listing.item_count": matched_count,
                "prez.rdf.quad_count": (
                    len(count_store) if count_store is not None else 0
                ),
                "await_duration_ms": count_await_ms,
            },
        )
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
            # This still returns an RDFlib graph of annotations, even when the store
            # is an Oxigraph Store.
            annotations_start = time.perf_counter()
            annotations_store = await return_annotated_rdf_for_oxigraph(
                item_store, data_repo, system_repo
            )
            log.debug(
                "OGC listing annotations completed",
                extra={
                    "event.name": "ogc_listing.annotations.complete",
                    "http.response.header.content-type": selected_mediatype,
                    "prez.annotation.quad_count": (
                        len(annotations_store) if annotations_store is not None else 0
                    ),
                    "operation_duration_ms": (time.perf_counter() - annotations_start)
                    * 1000,
                },
            )
    item_graph = item_store  # treat the Oxigraph Store as a graph

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
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "OGC JSON listing response completed",
            extra={
                "event.name": "ogc_listing.response.complete",
                "http.response.header.content-type": selected_mediatype,
                "prez.render.branch": "json",
                "duration_ms": total_ms,
            },
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
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "OGC GeoJSON listing response completed",
            extra={
                "event.name": "ogc_listing.response.complete",
                "http.response.header.content-type": selected_mediatype,
                "prez.render.branch": "geojson",
                "duration_ms": total_ms,
            },
        )
    elif selected_mediatype in NonAnnotatedRDFMediaType:
        item_store: OxiStore = item_graph
        dump_start = time.perf_counter()
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
        dump_ms = (time.perf_counter() - dump_start) * 1000
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "OGC non-annotated RDF listing response completed",
            extra={
                "event.name": "ogc_listing.response.complete",
                "http.response.header.content-type": selected_mediatype,
                "prez.render.branch": "non_annotated",
                "serialization_duration_ms": dump_ms,
                "duration_ms": total_ms,
            },
        )

    elif selected_mediatype in AnnotatedRDFMediaType:
        non_anot_mt = selected_mediatype.replace("anot+", "")
        default = OxiDefaultGraph()
        if item_store is None:
            # Item store could be None, if no queries were generated
            item_store = OxiStore()
        if annotations_store is not None:
            merge_start = time.perf_counter()
            item_store.bulk_extend(annotations_store)
            merge_ms = (time.perf_counter() - merge_start) * 1000
        else:
            merge_ms = 0.0
        serializer_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(
            str(non_anot_mt), RdfFormat.N_TRIPLES
        )
        oxigraph_prefixes = {
            p: str(n) for p, n in prefix_graph.namespace_manager.namespaces()
        }
        content = io.BytesIO()
        # TODO, what happens if the store has content in a named graph? This can only dump the default graph.
        dump_start = time.perf_counter()
        item_store.dump(
            content, serializer_format, from_graph=default, prefixes=oxigraph_prefixes
        )
        content.seek(0)  # Reset the stream position to the beginning
        dump_ms = (time.perf_counter() - dump_start) * 1000
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "OGC annotated RDF listing response completed",
            extra={
                "event.name": "ogc_listing.response.complete",
                "http.response.header.content-type": selected_mediatype,
                "prez.render.branch": "annotated",
                "merge_duration_ms": merge_ms,
                "serialization_duration_ms": dump_ms,
                "duration_ms": total_ms,
            },
        )
    return content, link_headers
