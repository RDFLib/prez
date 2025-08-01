import asyncio
import copy
import io
import json
import logging

from fastapi.responses import PlainTextResponse
from oxrdflib._converter import to_ox
from pyoxigraph import RdfFormat, Store as OxiStore, Quad as OxiQuad, NamedNode as OxiNamedNode, \
    BlankNode as OxiBlankNode, Literal as OxiLiteral, DefaultGraph as OxiDefaultGraph
from rdf2geojson import convert
from rdflib import Literal, DCTERMS, XSD, Namespace, URIRef
from rdflib.namespace import GEO, RDF, PROF
from sparql_grammar_pydantic import (
    IRI,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
)

from prez.cache import profiles_graph_cache, prefix_graph
from prez.config import settings
from prez.enums import NonAnnotatedRDFMediaType, AnnotatedRDFMediaType
from prez.exceptions.model_exceptions import PrefixNotBoundException
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
from prez.services.curie_functions import get_curie_id_for_uri, get_uri_for_curie_id
from prez.services.generate_queryables import generate_queryables_json
from prez.services.link_generation import add_prez_links_for_oxigraph
from prez.services.query_generation.count import CountQuery
from prez.services.query_generation.facet import FacetQuery
from prez.services.query_generation.shacl import NodeShape
from prez.services.query_generation.umbrella import (
    PrezQueryConstructor,
    merge_listing_query_grammar_inputs,
)

log = logging.getLogger(__name__)

DWC = Namespace("http://rs.tdwg.org/dwc/terms/")


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
    if (
        pmts.selected["mediatype"] == "application/geo+json"
    ):  # Ensure the focus nodes have a geometry in the SPARQL
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

    # add a count query if it's an annotated mediatype or counted search
    if (
            ("anot+" in pmts.selected["mediatype"] and not search_query) or
            (pmts.selected["mediatype"] == "application/geo+json") or
            (search_query and settings.search_uses_listing_count_limit)
    ):
        subselect = copy.deepcopy(main_query.inner_select)
        count_query = CountQuery(original_subselect=subselect).to_string()
        queries.append(count_query)
    facet_profile_uri = None
    if query_params.facet_profile:
        facet_profile_uri, facets_query = await _create_facets_query(
            main_query, query_params
        )
        if facets_query:
            queries.append(facets_query.to_string())

    item_store: OxiStore
    item_store, _ = await query_repo.send_queries(queries, [], return_oxigraph_store=True)
    default = OxiDefaultGraph()
    if facet_profile_uri:
        item_store.add(OxiQuad(OxiBlankNode(), OxiNamedNode(PREZ.facetProfile), OxiNamedNode(facet_profile_uri), default))
    if "anot+" in pmts.selected["mediatype"]:
        item_store.add(OxiQuad(OxiBlankNode(), OxiNamedNode(PREZ.currentProfile), OxiNamedNode(pmts.selected["profile"]), default))
        await add_prez_links_for_oxigraph(item_store, query_repo, endpoint_structure)

    # count search results - hard to do in SPARQL as the SELECT part of the query is NOT aggregated
    if search_query and not settings.search_uses_listing_count_limit:
        count = len(list(item_store.quads_for_pattern(None, OxiNamedNode(RDF.type), OxiNamedNode(PREZ.SearchResult), None)))
        if count == search_query.limit:
            count_literal = f">{(count - 1) * query_params.page}"
        else:
            # last page, this is the actual count = (complete pages) * limit + count
            count_literal = f"{(query_params.limit * (query_params.page - 1)) + count}"
        item_store.add(OxiQuad(OxiNamedNode(PREZ.SearchResult), OxiNamedNode(PREZ["count"]), OxiLiteral(count_literal), default))
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


async def _create_facets_query(main_query, query_params):
    profile_uri = await get_facet_profile_uri_from_qsa(query_params.facet_profile)
    if not profile_uri:
        return None, None
    else:
        facet_nodeshape = NodeShape(
            uri=profile_uri,
            graph=profiles_graph_cache,
            kind="profile",
            focus_node=Var(value="focus_node"),
        )
        facet_property_shape = facet_nodeshape.propertyShapes[0]
        subselect_for_faceting = copy.deepcopy(main_query.inner_select)
        facets_query = FacetQuery(
            original_subselect=subselect_for_faceting,
            property_shape=facet_property_shape,
        )
        return profile_uri, facets_query


async def get_facet_profile_uri_from_qsa(facet_profile_qsa):
    requested_facet_profile = facet_profile_qsa
    profile_uri = next(  # check if QSA is identifier
        profiles_graph_cache.subjects(
            predicate=DCTERMS.identifier, object=Literal(requested_facet_profile)
        ),
        None,
    ) or next(
        profiles_graph_cache.subjects(
            predicate=DCTERMS.identifier,
            object=Literal(requested_facet_profile, datatype=XSD.token),
        ),
        None,
    )
    if not profile_uri:  # check if QSA is uri
        try:
            uri_ref = URIRef(requested_facet_profile)
            # Check if this URI exists as a subject in any triple
            if (uri_ref, None, None) in profiles_graph_cache:
                profile_uri = uri_ref
        except ValueError:
            pass

    if not profile_uri:  # check if QSA is curie
        try:
            requested_facet_profile_uri = await get_uri_for_curie_id(
                requested_facet_profile
            )
            if requested_facet_profile_uri:
                if (requested_facet_profile_uri, None, None) in profiles_graph_cache:
                    profile_uri = requested_facet_profile_uri
        except PrefixNotBoundException:
            pass
    return profile_uri


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
    count = 0
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

    queries = []
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
        queries.append(feature_list_query.to_string())

        # add the count query
        subselect = copy.deepcopy(feature_list_query.inner_select)
        count_query = CountQuery(original_subselect=subselect).to_string()
    link_headers = None
    if selected_mediatype == "application/sparql-query":
        # just do the first query for now:
        content = io.BytesIO(queries[0].encode("utf-8"))
        return content, link_headers
    count: int

    item_store: OxiStore
    main_query_task = asyncio.ensure_future(data_repo.send_queries(queries, [], return_oxigraph_store=True))
    if count_query:
        # send this in parallel to the main query
        count_query_task = asyncio.ensure_future(data_repo.send_queries([count_query], [], return_oxigraph_store=True))
    else:
        count_query_task = None
    await asyncio.sleep(0)  # Yield control to allow the parallel tasks to start
    item_store, _ = await main_query_task
    if count_query_task is not None:
        count_store: OxiStore
        count_store, _ = await count_query_task
        if count_store is not None:
            for q in count_store.quads_for_pattern(None, None, None, None):
                count_str = str(q[2].value)
                count = get_geojson_int_count(count_str)
                break
            else:
                count = 0
    # only need the annotations for mediatypes of application/json or annotated mediatypes
    annotations_store = None
    annotations_graph = None
    if (
        (selected_mediatype in AnnotatedRDFMediaType)
        or (selected_mediatype == "application/json")
        or (
            selected_mediatype == "application/geo+json"
            and "human" in profile_nodeshape.uri.lower()
        )
    ):
        # This still returns an RDFlib graph of anotations, even when the store is an Oxigraph Store.
        annotations_store = await return_annotated_rdf_for_oxigraph(
            item_store, data_repo, system_repo
        )
    item_graph = item_store # treat the Oxigraph Store as a graph

    if selected_mediatype == "application/json":
        if endpoint_uri_type[0] in [
            OGCFEAT["queryables-local"],
            OGCFEAT["queryables-global"],
        ]:
            if queryables:  # queryables were generated from SHACL
                pass
            else:  # generate them from the data
                queryables = generate_queryables_json(
                    item_store, annotations_store, url, endpoint_uri_type[0]
                )
                content = io.BytesIO(
                    queryables.model_dump_json(exclude_none=True, by_alias=True).encode(
                        "utf-8"
                    )
                )
        else:
            collections = create_collections_json(
                item_graph,
                annotations_store if annotations_store is not None else annotations_graph,
                url,
                selected_mediatype,
                query_params,
                count,
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

    elif selected_mediatype == "application/geo+json":
        if "human" in profile_nodeshape.uri.lower():  # human readable profile
            item_store: OxiStore = item_graph
            if annotations_store is not None:
                item_store.bulk_extend(annotations_store)
            elif annotations_graph is not None:
                default = OxiDefaultGraph()
                for s, p, o in annotations_graph.triples((None, None, None)):
                    item_store.add(OxiQuad(to_ox(s), to_ox(p), to_ox(o), default))
            kind = "human"
        else:
            kind = "machine"
        geojson = convert(
            g=item_store,
            do_validate=False,
            iri2id=get_curie_id_for_uri,
            kind=kind,
            fc_uri=collection_uri,
            namespace_manager=prefix_graph.namespace_manager,
        )
        link_headers, geojson = await generate_geojson_extras(
            count, geojson, query_params, selected_mediatype, url
        )
        content = io.BytesIO(json.dumps(geojson).encode("utf-8"))
    elif selected_mediatype in NonAnnotatedRDFMediaType:
        item_store: OxiStore = item_graph
        serializer_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(str(selected_mediatype), RdfFormat.N_TRIPLES)
        oxigraph_prefixes = {p: str(n) for p, n in prefix_graph.namespace_manager.namespaces()}
        content = io.BytesIO()
        # TODO, what happens if the store has content in a named graph? This can only dump the default graph.
        item_store.dump(content, serializer_format, from_graph=OxiDefaultGraph(), prefixes=oxigraph_prefixes)
        content.seek(0)  # Reset the stream position to the beginning

    elif selected_mediatype in AnnotatedRDFMediaType:
        non_anot_mt = selected_mediatype.replace("anot+", "")
        item_store: OxiStore = item_graph
        default = OxiDefaultGraph()
        if annotations_store is not None:
            item_store.bulk_extend(annotations_store)
        elif annotations_graph is not None:
            # Add the annotations to the store
            for s, p, o in annotations_graph.triples((None, None, None)):
                item_store.add(OxiQuad(to_ox(s), to_ox(p), to_ox(o), default))
        serializer_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(str(non_anot_mt), RdfFormat.N_TRIPLES)
        oxigraph_prefixes = {p: str(n) for p, n in prefix_graph.namespace_manager.namespaces()}
        content = io.BytesIO()
        # TODO, what happens if the store has content in a named graph? This can only dump the default graph.
        item_store.dump(content, serializer_format, from_graph=default, prefixes=oxigraph_prefixes)
        content.seek(0)  # Reset the stream position to the beginning
        content = io.BytesIO(item_graph.serialize(format=non_anot_mt, encoding="utf-8"))
    return content, link_headers
