import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, Request
from pyoxigraph import Store, RdfFormat, DefaultGraph as OxiDefaultGraph
from rdflib import DCTERMS, RDF, SH, SKOS, Literal, URIRef, Graph
from sparql_grammar import IRI, Var

from prez.cache import (
    annotations_store,
    endpoints_graph_cache,
    oxrdflib_store,
    prez_system_graph,
    profiles_graph_cache,
    queryable_props,
    store,
    system_store,
    persistent_store,
)
from prez.config import Settings, settings, get_reference_data_dir
from prez.enums import (
    GeoJSONMediaType,
    JSONMediaType,
    NonAnnotatedRDFMediaType,
    SPARQLQueryMediaType,
    AnnotatedRDFMediaType,
)
from prez.enums import SearchMethod
from prez.exceptions.model_exceptions import (
    NoEndpointNodeshapeException,
    URINotFoundException,
    MissingFilterQueryError,
)
from prez.models.query_params import (
    ListingQueryParams,
    ObjectQueryParams,
    parse_datetime,
)
from prez.reference_data.prez_ns import ALTREXT, EP, OGCE, OGCFEAT, ONT
from prez.repositories import OxrdflibRepo, PyoxigraphRepo, RemoteSparqlRepo, Repo
from prez.services.classes import get_classes_single
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.search_default import SearchQueryRegex
from prez.services.query_generation.search_fuseki_fts import SearchQueryFusekiFTS
from prez.services.query_generation.search_jena_lucene import SearchQueryJenaLucene
from prez.services.query_generation.shacl import (
    FTSUnionContainer,
    NodeShape,
    PropertyShape,
    get_nodeshape,
)

logger = logging.getLogger(__name__)


async def get_async_http_client():
    return httpx.AsyncClient(
        auth=(
            (settings.sparql_username, settings.sparql_password)
            if settings.sparql_username
            else None
        ),
        timeout=settings.sparql_timeout,
    )


def get_pyoxi_memory_store():
    logger.info("Using in-memory pyoxigraph data store")
    return store


def get_pyoxi_persistent_store():
    global persistent_store
    if persistent_store is None:
        oxigraph_data_dir = Path(settings.pyoxigraph_data_dir)
        if not oxigraph_data_dir.exists():
            raise FileNotFoundError(
                f"Pyoxigraph data directory {oxigraph_data_dir} does not exist"
            )
        logger.info(f"Using pyoxigraph data store {oxigraph_data_dir}")
        persistent_store = Store(path=str(oxigraph_data_dir))
    return persistent_store


def get_pyoxi_store():
    if settings.sparql_repo_type == "pyoxigraph_persistent":
        return get_pyoxi_persistent_store()
    return get_pyoxi_memory_store()


def get_system_store():
    return system_store


def get_annotations_store():
    return annotations_store


def get_oxrdflib_store():
    return oxrdflib_store


def get_queryable_props():
    return queryable_props


async def get_data_repo(
    request: Request,
    pyoxi_data_store: Store = Depends(get_pyoxi_store),
    pyoxi_system_store: Store = Depends(get_system_store),
) -> Repo:
    if URIRef(request.scope.get("route").name) in settings.system_endpoints:
        return PyoxigraphRepo(pyoxi_system_store)
    try:
        data_repo = request.app.state.repo
        return data_repo
    except (AttributeError, LookupError):
        pass
    if (
        settings.sparql_repo_type == "pyoxigraph_memory"
        or settings.sparql_repo_type == "pyoxigraph_persistent"
    ):
        return PyoxigraphRepo(pyoxi_data_store)
    elif settings.sparql_repo_type == "oxrdflib":
        return OxrdflibRepo(oxrdflib_store)
    elif settings.sparql_repo_type == "remote":
        try:
            http_async_client = request.app.state.http_async_client
        except (AttributeError, LookupError):
            http_async_client = await get_async_http_client()
        return RemoteSparqlRepo(http_async_client)


async def get_system_repo(
    pyoxi_store: Store = Depends(get_system_store),
) -> Repo:
    """
    A pyoxigraph Store with Prez system data including:
    - Profiles
    # TODO add and test other system data (endpoints etc.)
    """
    return PyoxigraphRepo(pyoxi_store)


async def get_annotations_repo():
    """
    A pyoxigraph Store with labels, descriptions etc. from Context Ontologies
    """
    return PyoxigraphRepo(annotations_store)


def get_runtime_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", settings)


async def load_local_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    default = OxiDefaultGraph()
    for file in (Path(__file__).parent.parent / settings.pyoxigraph_data_dir).glob(
        "**/*.ttl"
    ):
        try:
            store.bulk_load(None, RdfFormat.TURTLE, path=str(file), to_graph=default)
        except Exception as e:
            raise SyntaxError(f"Error parsing file {file}: {e}")


async def load_system_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    profiles_bytes = profiles_graph_cache.serialize(format="nt", encoding="utf-8")
    store.load(profiles_bytes, RdfFormat.N_TRIPLES)

    endpoints_bytes = endpoints_graph_cache.serialize(format="nt", encoding="utf-8")
    store.load(endpoints_bytes, RdfFormat.N_TRIPLES)

    prez_system_graph_bytes = prez_system_graph.serialize(format="nt", encoding="utf-8")
    store.load(prez_system_graph_bytes, RdfFormat.N_TRIPLES)


async def load_annotations_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    default = OxiDefaultGraph()
    annotations_dir = get_reference_data_dir() / "annotations"
    for file in annotations_dir.glob("*.nt"):
        store.bulk_load(None, RdfFormat.N_TRIPLES, path=str(file), to_graph=default)
    for file in annotations_dir.glob("*.ttl"):
        store.bulk_load(None, RdfFormat.TURTLE, path=str(file), to_graph=default)
    for file in annotations_dir.glob("*.nq"):
        store.bulk_load(None, RdfFormat.N_QUADS, path=str(file))
    for file in annotations_dir.glob("*.trig"):
        store.bulk_load(None, RdfFormat.TRIG, path=str(file))


async def get_endpoint_uri_type(
    request: Request,
    system_repo: Repo = Depends(get_system_repo),
) -> tuple[URIRef, URIRef]:
    """
    Returns the URI of the endpoint and its type (ObjectEndpoint or ListingEndpoint)
    """
    endpoint_uri = URIRef(request.scope.get("route").name)
    ep_type_fs = await get_classes_single(endpoint_uri, system_repo)
    ep_types = list(ep_type_fs)

    # Iterate over each item in ep_types
    for ep_type in ep_types:
        # Check if the current ep_type is either ObjectEndpoint or ListingEndpoint
        if ep_type in [ONT.ObjectEndpoint, ONT.ListingEndpoint]:
            return endpoint_uri, ep_type
    raise ValueError(
        "Endpoint must be declared as either a 'https://prez.dev/ont/ObjectEndpoint' or a "
        "'https://prez.dev/ont/ListingEndpoint' in order for the appropriate profile to be determined."
    )


async def cql_post_parser_dependency(
    request: Request,
    queryable_props: list = Depends(get_queryable_props),
) -> CQLParser:
    """
    CQL parser for POST /cql.

    BREAKING CHANGE: The body must now be a JSON object with a ``filter`` key
    containing the CQL2-JSON expression.  The previous format (raw CQL expression
    as the entire body) is no longer supported.

    Example body::

        {"filter": {"op": "s_intersects", "args": [...]}, "limit": 10}
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json",
        )
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object with a 'filter' key.",
        )

    cql_json = body.get("filter")
    if cql_json is None:
        raise HTTPException(
            status_code=400,
            detail="Request body must contain a 'filter' key with the CQL2-JSON expression.",
        )

    try:
        cql_parser = CQLParser(cql_json=cql_json, queryable_props=queryable_props)
        cql_parser.parse()
        return cql_parser
    except Exception as e:
        error_msg = e.args[0] if e.args else "Error parsing CQL."
        raise HTTPException(status_code=400, detail=error_msg)


async def cql_get_parser_dependency(
    query_params: ListingQueryParams = Depends(),
    queryable_props: list = Depends(get_queryable_props),
    endpoint_uri_type: str = Depends(get_endpoint_uri_type),
    runtime_settings: Settings = Depends(get_runtime_settings),
) -> CQLParser:
    if _search_uses_jena_lucene(endpoint_uri_type[0], runtime_settings):
        if query_params._filter:
            _parse_lucene_filter_json(query_params._filter, "GET")
        return None

    if query_params._filter:
        try:
            crs = query_params.filter_crs
            query = json.loads(query_params._filter)
            cql_parser = CQLParser(
                cql_json=query, crs=crs, queryable_props=queryable_props
            )
            try:
                cql_parser.parse()
            except Exception as e:
                raise e
            return cql_parser
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format.")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="Invalid CQL format: Parsing failed."
            )
    elif endpoint_uri_type[0] == URIRef(
        "https://prez.dev/endpoint/extended-ogc-records/cql-get"
    ):
        raise MissingFilterQueryError(
            "filter query parameter with a valid CQL JSON expression must be provided when "
            "using the /cql endpoint."
        )


async def get_unprefixed_url_path(
    request: Request,
) -> str:
    root_path = request.scope.get("app_root_path", request.scope.get("root_path", ""))
    return request.url.path[len(root_path) :]


########################################################################################################################
# POST support: shared body-parsing helper
########################################################################################################################


def _validate_post_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json",
        )


async def _parse_post_body(request: Request) -> dict:
    """Parse and validate the JSON body of a POST request, returning a dict."""
    _validate_post_content_type(request)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object.",
        )
    return body


def _is_absolute_iri(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.path))


def _collect_non_iri_cql_properties(node, invalid_properties: list[str]) -> None:
    if isinstance(node, dict):
        property_value = node.get("property")
        if property_value is not None:
            if not isinstance(property_value, str) or not _is_absolute_iri(
                property_value
            ):
                invalid_properties.append(str(property_value))
        for value in node.values():
            _collect_non_iri_cql_properties(value, invalid_properties)
    elif isinstance(node, list):
        for item in node:
            _collect_non_iri_cql_properties(item, invalid_properties)


def _validate_lucene_cql_filter(filter_json: dict | None) -> None:
    if filter_json is None:
        return
    invalid_properties: list[str] = []
    _collect_non_iri_cql_properties(filter_json, invalid_properties)
    if invalid_properties:
        invalid_values = ", ".join(dict.fromkeys(invalid_properties))
        raise HTTPException(
            status_code=400,
            detail=(
                "CQL property values must be IRIs when the Lucene-backed /cql "
                f"feature is enabled. Invalid values: {invalid_values}"
            ),
        )


async def _get_facetable_lucene_queryables(system_repo: Repo) -> set[str]:
    query = f"""
    CONSTRUCT {{
        ?queryable <{ONT.facetable}> ?facetable .
    }}
    WHERE {{
        ?queryable a <http://www.opengis.net/doc/IS/cql2/1.0/Queryable> ;
            <{ONT.facetable}> ?facetable .
    }}
    """
    graph = await system_repo.rdf_query_to_rdflib_graph(query)
    supported: set[str] = set()
    for subject, _, facetable in graph.triples(
        (None, URIRef(str(ONT.facetable)), None)
    ):
        if str(facetable).lower() in {"true", "1"}:
            supported.add(str(subject))
    return supported


async def _validate_lucene_requested_facets(
    facets: list[str] | None,
    system_repo: Repo,
) -> list[str] | None:
    if not facets:
        return None
    supported = await _get_facetable_lucene_queryables(system_repo)
    unsupported = [facet for facet in facets if facet not in supported]
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported facet IRIs: {', '.join(unsupported)}",
        )
    return facets


async def lucene_cql_get_facets_dependency(
    request: Request,
    query_params: ListingQueryParams = Depends(),
    system_repo: Repo = Depends(get_system_repo),
) -> list[str] | None:
    facets = request.query_params.getlist("facets") or None
    if facets and query_params.facet_profile:
        raise HTTPException(
            status_code=400,
            detail="Lucene-backed /cql cannot accept both 'facets' and 'facet_profile'.",
        )
    return await _validate_lucene_requested_facets(facets, system_repo)


async def lucene_cql_post_facets_dependency(
    request: Request,
    system_repo: Repo = Depends(get_system_repo),
) -> list[str] | None:
    body = await _parse_post_body(request)
    facets = body.get("facets")
    if facets is None:
        return None
    if body.get("facet_profile"):
        raise HTTPException(
            status_code=400,
            detail="Lucene-backed /cql cannot accept both 'facets' and 'facet_profile'.",
        )
    if not isinstance(facets, list) or any(
        not isinstance(facet, str) for facet in facets
    ):
        raise HTTPException(
            status_code=400,
            detail="POST facets must be an array of IRI strings.",
        )
    return await _validate_lucene_requested_facets(facets, system_repo)


def _parse_lucene_filter_json(
    filter_value,
    source: str,
) -> dict | None:
    if filter_value is None:
        return None
    if isinstance(filter_value, str):
        try:
            filter_json = json.loads(filter_value)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, detail=f"Invalid {source} filter JSON."
            )
    else:
        filter_json = filter_value
    if not isinstance(filter_json, dict):
        raise HTTPException(
            status_code=400,
            detail=f"{source} filter must be a JSON object.",
        )
    _validate_lucene_cql_filter(filter_json)
    return filter_json


def _calculate_listing_offset(query_params: ListingQueryParams) -> int:
    if query_params.offset is not None:
        return int(query_params.offset)
    if query_params.startindex is not None:
        return int(query_params.startindex)
    return int(query_params.limit) * (int(query_params.page) - 1)


def _resolve_lucene_hit_limit(
    query_params: ListingQueryParams,
    runtime_settings: Settings,
) -> int:
    if runtime_settings.fts_limit is not None:
        return int(runtime_settings.fts_limit)
    return int(query_params.limit)


def _lucene_uses_limit_offset_pushdown(runtime_settings: Settings) -> bool:
    return bool(runtime_settings.lucene_limit_offset_pushdown)


def _normalize_lucene_search_fields(
    fields,
    source: str,
) -> str | list[str] | None:
    if fields is None:
        return None
    if isinstance(fields, str):
        normalized = fields.strip()
        if not normalized:
            raise HTTPException(
                status_code=400,
                detail=f"{source} fields must be 'default' or a non-empty string/list.",
            )
        return normalized if normalized == "default" else [normalized]
    if isinstance(fields, list):
        normalized = []
        for field in fields:
            if not isinstance(field, str) or not field.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"{source} fields must be 'default' or a non-empty string/list.",
                )
            normalized.append(field.strip())
        if not normalized:
            raise HTTPException(
                status_code=400,
                detail=f"{source} fields must be 'default' or a non-empty string/list.",
            )
        if "default" in normalized:
            if len(normalized) > 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"{source} fields cannot mix 'default' with explicit field names.",
                )
            return "default"
        return normalized
    raise HTTPException(
        status_code=400,
        detail=f"{source} fields must be 'default' or a non-empty string/list.",
    )


def _resolve_lucene_search_fields(
    override_fields,
    runtime_settings: Settings,
    source: str,
) -> str | list[str]:
    normalized_override = _normalize_lucene_search_fields(override_fields, source)
    if normalized_override is not None:
        return normalized_override
    return runtime_settings.lucene_search_fields


def _search_uses_jena_lucene(endpoint_uri: URIRef, runtime_settings: Settings) -> bool:
    return runtime_settings.enable_cql_jena_lucene_json and endpoint_uri in {
        EP["extended-ogc-records/search"],
        EP["extended-ogc-records/search-post"],
    }


async def lucene_cql_get_parser_dependency(
    request: Request,
    query_params: ListingQueryParams = Depends(),
    runtime_settings: Settings = Depends(get_runtime_settings),
    facets: list[str] | None = Depends(lucene_cql_get_facets_dependency),
) -> CQLParser | None:
    _ = facets
    _parse_lucene_filter_json(query_params._filter, "GET")
    return None


async def generate_lucene_cql_search_query(
    request: Request,
    query_params: ListingQueryParams = Depends(),
    runtime_settings: Settings = Depends(get_runtime_settings),
    facets: list[str] | None = Depends(lucene_cql_get_facets_dependency),
):
    _ = facets
    filter_json = _parse_lucene_filter_json(query_params._filter, "GET")
    search_fields = _resolve_lucene_search_fields(
        request.query_params.getlist("fields") or None,
        runtime_settings,
        "GET",
    )
    return SearchQueryJenaLucene(
        term=query_params.q,
        facets=facets,
        filter_json=filter_json,
        limit=int(query_params.limit),
        offset=_calculate_listing_offset(query_params),
        lucene_index_name=runtime_settings.lucene_index_name,
        search_fields=search_fields,
        lucene_hit_limit=_resolve_lucene_hit_limit(query_params, runtime_settings),
        order_by=query_params.order_by,
        order_by_direction=query_params.order_by_direction,
        include_matches=bool(query_params.q),
        pagination_pushed_down=_lucene_uses_limit_offset_pushdown(runtime_settings),
    )


########################################################################################################################
# POST support: listing endpoints
########################################################################################################################


async def listing_post_params_dependency(request: Request) -> ListingQueryParams:
    """
    Parse a JSON POST body and return a ``ListingQueryParams`` equivalent.

    The body fields mirror the GET query parameter names::

        {
            "_mediatype": "text/turtle",
            "_profile": "https://example.org/profile",
            "page": 1,
            "limit": 10,
            "q": "search term",
            "fields": ["urn:jena:lucene:field#id"],
            "filter": { ... CQL2-JSON ... },
            "filter-lang": "cql2-json",
            "filter_crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            "bbox": [153.0, -28.0, 154.0, -27.0],
            "datetime": "2020-01-01T00:00:00Z/2021-01-01T00:00:00Z",
            "order_by": "label",
            "order_by_direction": "ASC"
        }
    """
    body = await _parse_post_body(request)

    # bbox
    bbox_raw = body.get("bbox")
    if bbox_raw is not None:
        if not isinstance(bbox_raw, list):
            raise HTTPException(
                status_code=400, detail="bbox must be an array of coordinates."
            )
        try:
            coords = [float(v) for v in bbox_raw]
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="bbox coordinates must be numbers.",
            )
        if len(coords) not in (4, 6):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid bbox: expected 4 or 6 coordinates, got {len(coords)}.",
            )
        bbox = coords
    else:
        bbox = None

    # datetime
    datetime_raw = body.get("datetime")
    if datetime_raw:
        try:
            dt = parse_datetime(str(datetime_raw))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid datetime: {exc}")
    else:
        dt = None

    # filter (dict → JSON string to reuse existing validation)
    filter_raw = body.get("filter")
    if filter_raw is not None:
        if isinstance(filter_raw, str):
            filter_str = filter_raw
        else:
            filter_str = json.dumps(filter_raw)
    else:
        filter_str = None

    # Pagination
    page = body.get("page", 1)
    limit = body.get("limit", 10)
    offset = body.get("offset")
    startindex = body.get("startindex")

    # Build params object without going through FastAPI's Query injection
    params = ListingQueryParams.__new__(ListingQueryParams)
    params.mediatype = body.get("_mediatype")
    params.profile = body.get("_profile")
    params.page = page
    params.limit = limit
    params.offset = offset
    params.startindex = startindex
    params.facet_profile = body.get("facet_profile")
    params.bbox = bbox
    params.filter_lang = body.get("filter-lang", "cql2-json")
    params.filter_crs = body.get(
        "filter_crs", "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    )
    params.datetime = dt
    params.order_by = body.get("order_by")
    params.order_by_direction = body.get("order_by_direction")
    params._filter = filter_str
    params.q = body.get("q")
    params.fields = body.get("fields")
    params.predicates = body.get("predicates", [])
    params.subscription_key = body.get("subscription-key")

    params.validate_pagination_params()
    params.validate_filter()
    return params


async def lucene_cql_post_parser_dependency(
    request: Request,
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),
    runtime_settings: Settings = Depends(get_runtime_settings),
    facets: list[str] | None = Depends(lucene_cql_post_facets_dependency),
) -> CQLParser | None:
    body = await _parse_post_body(request)
    if body.get("q") is not None and not isinstance(body.get("q"), str):
        raise HTTPException(status_code=400, detail="POST q must be a string.")
    _ = facets
    _parse_lucene_filter_json(body.get("filter"), "POST")
    return None


async def generate_lucene_cql_search_query_post(
    request: Request,
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),
    runtime_settings: Settings = Depends(get_runtime_settings),
    facets: list[str] | None = Depends(lucene_cql_post_facets_dependency),
):
    body = await _parse_post_body(request)
    q = body.get("q")
    if q is not None and not isinstance(q, str):
        raise HTTPException(status_code=400, detail="POST q must be a string.")
    _ = facets
    filter_json = _parse_lucene_filter_json(body.get("filter"), "POST")
    search_fields = _resolve_lucene_search_fields(
        body.get("fields"),
        runtime_settings,
        "POST",
    )
    return SearchQueryJenaLucene(
        term=q,
        facets=facets,
        filter_json=filter_json,
        limit=int(query_params.limit),
        offset=_calculate_listing_offset(query_params),
        lucene_index_name=runtime_settings.lucene_index_name,
        search_fields=search_fields,
        lucene_hit_limit=_resolve_lucene_hit_limit(query_params, runtime_settings),
        order_by=query_params.order_by,
        order_by_direction=query_params.order_by_direction,
        include_matches=bool(q),
        pagination_pushed_down=_lucene_uses_limit_offset_pushdown(runtime_settings),
    )


async def get_negotiated_pmts_listing_post(
    request: Request,
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: tuple = Depends(get_endpoint_uri_type),
    url_path: str = Depends(get_unprefixed_url_path),
) -> "NegotiatedPMTs":
    """POST variant of get_negotiated_pmts for listing endpoints."""
    from sparql_grammar import Var
    from prez.services.connegp_service import NegotiatedPMTs

    # For listing endpoints, focus node is always a variable (not a specific IRI)
    focus_node = Var(value="focus_node")
    endpoint_ns = await get_endpoint_nodeshapes(
        request=request,
        repo=repo,
        system_repo=system_repo,
        endpoint_uri_type=endpoint_uri_type,
        focus_node=focus_node,
        url_path=url_path,
    )
    klasses = endpoint_ns.targetClasses
    params_dict = {
        "_profile": query_params.profile or "",
        "_mediatype": query_params.mediatype or "",
    }
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=params_dict,
        classes=klasses,
        listing=True,
        system_repo=system_repo,
        current_path=url_path,
    )
    await pmts.setup()
    return pmts


async def get_endpoint_structure_listing_post(
    pmts: "NegotiatedPMTs" = Depends(get_negotiated_pmts_listing_post),
    endpoint_uri_type: tuple = Depends(get_endpoint_uri_type),
) -> tuple:
    from prez.reference_data.prez_ns import ALTREXT

    endpoint_uri = endpoint_uri_type[0]
    if (endpoint_uri in settings.system_endpoints) or (
        pmts.selected.get("profile") == ALTREXT["alt-profile"]
    ):
        return ("profiles",)
    return settings.endpoint_structure


async def get_profile_nodeshape_listing_post(
    pmts: "NegotiatedPMTs" = Depends(get_negotiated_pmts_listing_post),
) -> "NodeShape":
    from sparql_grammar import Var
    from prez.cache import profiles_graph_cache
    from prez.services.query_generation.shacl import get_nodeshape

    profile = pmts.selected.get("profile")
    focus_node = Var(value="focus_node")  # always Var for listing
    return get_nodeshape(
        uri=profile,
        graph=profiles_graph_cache,
        kind="profile",
        focus_node=focus_node,
    )


async def cql_post_listing_parser_dependency(
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),
    queryable_props: list = Depends(get_queryable_props),
    endpoint_uri_type: tuple = Depends(get_endpoint_uri_type),
    runtime_settings: Settings = Depends(get_runtime_settings),
) -> "CQLParser | None":
    """CQL parser for listing POST endpoints (filter is optional)."""
    if _search_uses_jena_lucene(endpoint_uri_type[0], runtime_settings):
        if query_params._filter:
            _parse_lucene_filter_json(query_params._filter, "POST")
        return None

    if query_params._filter:
        try:
            crs = query_params.filter_crs
            cql_json = json.loads(query_params._filter)
            cql_parser = CQLParser(
                cql_json=cql_json, crs=crs, queryable_props=queryable_props
            )
            cql_parser.parse()
            return cql_parser
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, detail="Invalid JSON in 'filter' field."
            )
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid CQL format: parsing failed."
            )
    return None


async def generate_search_query_post(
    request: Request,
    query_params: ListingQueryParams = Depends(listing_post_params_dependency),
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: tuple = Depends(get_endpoint_uri_type),
    runtime_settings: Settings = Depends(get_runtime_settings),
):
    """POST variant of generate_search_query — reads params from POST body."""
    term = query_params.q

    def has_filtering_params() -> bool:
        if query_params.facet_profile:
            return True
        if query_params._filter:
            return True
        if query_params.bbox:
            return True
        if query_params.datetime:
            return True
        return False

    _search_ep_uris = {
        EP["extended-ogc-records/search"],
        EP["extended-ogc-records/search-post"],
    }
    if not term:
        if endpoint_uri_type[0] in _search_ep_uris:
            if has_filtering_params():
                if _search_uses_jena_lucene(endpoint_uri_type[0], runtime_settings):
                    body = await _parse_post_body(request)
                    filter_json = _parse_lucene_filter_json(
                        query_params._filter, "POST"
                    )
                    search_fields = _resolve_lucene_search_fields(
                        body.get("fields"),
                        runtime_settings,
                        "POST",
                    )
                    return SearchQueryJenaLucene(
                        term=query_params.q,
                        facets=None,
                        filter_json=filter_json,
                        limit=int(query_params.limit),
                        offset=_calculate_listing_offset(query_params),
                        lucene_index_name=runtime_settings.lucene_index_name,
                        search_fields=search_fields,
                        lucene_hit_limit=_resolve_lucene_hit_limit(
                            query_params, runtime_settings
                        ),
                        order_by=query_params.order_by,
                        order_by_direction=query_params.order_by_direction,
                        include_matches=bool(query_params.q),
                        pagination_pushed_down=_lucene_uses_limit_offset_pushdown(
                            runtime_settings
                        ),
                    )
                return DummySearchMarker()
            raise HTTPException(
                status_code=400,
                detail=(
                    "Search query parameter 'q' must be provided in the request body, "
                    "or use filtering parameters (facet_profile, filter, bbox, datetime)."
                ),
            )
        return None

    if _search_uses_jena_lucene(endpoint_uri_type[0], runtime_settings):
        body = await _parse_post_body(request)
        filter_json = _parse_lucene_filter_json(query_params._filter, "POST")
        search_fields = _resolve_lucene_search_fields(
            body.get("fields"),
            runtime_settings,
            "POST",
        )
        return SearchQueryJenaLucene(
            term=term,
            facets=None,
            filter_json=filter_json,
            limit=int(query_params.limit),
            offset=_calculate_listing_offset(query_params),
            lucene_index_name=runtime_settings.lucene_index_name,
            search_fields=search_fields,
            lucene_hit_limit=_resolve_lucene_hit_limit(query_params, runtime_settings),
            order_by=query_params.order_by,
            order_by_direction=query_params.order_by_direction,
            include_matches=bool(term),
            pagination_pushed_down=_lucene_uses_limit_offset_pushdown(runtime_settings),
        )

    predicates = query_params.predicates if hasattr(query_params, "predicates") else []
    page = query_params.page or 1
    limit = query_params.limit if query_params.limit else settings.search_count_limit
    offset = limit * (page - 1)

    if settings.search_method == SearchMethod.DEFAULT:
        return SearchQueryRegex(
            term=term,
            predicates=predicates,
            limit=limit,
            offset=offset,
        )
    elif settings.search_method == SearchMethod.FTS_FUSEKI:
        predicates = predicates if predicates else settings.search_predicates
        shacl_shapes = await get_jena_fts_shacl_predicates(system_repo)

        def _has_triple(graph, s, p, o) -> bool:
            return any(graph.triples((s, p, o)))

        shacl_shape_ids = [
            str(x)
            for x in shacl_shapes.objects(subject=None, predicate=DCTERMS.identifier)
        ]
        tssp_lists = []
        tss_list = []
        non_shacl_predicates = []
        i = 100
        for pred in predicates:
            if str(pred) in shacl_shape_ids:
                shacl_shape_uri = shacl_shapes.value(
                    subject=None,
                    predicate=DCTERMS.identifier,
                    object=Literal(pred),
                )
                if (
                    shacl_shape_uri
                    and _has_triple(
                        shacl_shapes, shacl_shape_uri, RDF.type, ONT.JenaFTSUnionShape
                    )
                    and _has_triple(shacl_shapes, shacl_shape_uri, SH.union, None)
                ):
                    union_container = FTSUnionContainer(
                        uri=shacl_shape_uri,
                        graph=shacl_shapes,
                        focus_node=Var(value="focus_node"),
                        shape_number=i,
                    )
                    tssp_lists.extend(union_container.tssp_list_with_preds)
                    tss_list.extend(union_container.tss_list)
                    i = union_container.next_shape_number
                else:
                    shacl_shape_g = shacl_shapes.cbd(shacl_shape_uri)
                    search_preds = list(
                        shacl_shape_g.objects(
                            subject=None, predicate=ONT.searchPredicate
                        )
                    )
                    ps = PropertyShape(
                        uri=shacl_shape_uri,
                        graph=shacl_shape_g,
                        kind="fts",
                        focus_node=Var(value="focus_node"),
                        shape_number=i,
                    )
                    tssp_lists.append(
                        (ps.tssp_list, search_preds, ps.focus_node_classes)
                    )
                    tss_list.extend(ps.tss_list)
                    i += 1
            else:
                non_shacl_predicates.append(pred)

        return SearchQueryFusekiFTS(
            term=term,
            non_shacl_predicates=non_shacl_predicates,
            shacl_tssp_preds=tssp_lists,
            tss_list=tss_list,
            limit=limit,
            offset=offset,
            fts_limit=settings.fts_limit,
        )
    raise NotImplementedError(f"Search method {settings.search_method} not implemented")


########################################################################################################################
# POST support: /object endpoint
########################################################################################################################


async def object_post_params_dependency(request: Request) -> dict:
    """Parse the JSON body for POST /object, returning the raw body dict."""
    return await _parse_post_body(request)


async def get_focus_node_post_object(
    body: dict = Depends(object_post_params_dependency),
) -> "IRI":
    from sparql_grammar import IRI as SPARQLIRI

    iri = body.get("iri") or body.get("uri")
    if not iri:
        raise HTTPException(
            status_code=400,
            detail="Request body must contain 'iri' or 'uri'.",
        )
    return SPARQLIRI(value=iri)


async def get_endpoint_nodeshapes_post_object(
    focus_node=Depends(get_focus_node_post_object),
) -> "NodeShape":
    from prez.cache import endpoints_graph_cache
    from prez.services.query_generation.shacl import get_nodeshape

    return get_nodeshape(
        uri=URIRef("http://example.org/ns#Object"),
        graph=endpoints_graph_cache,
        kind="endpoint",
        focus_node=focus_node,
    )


async def get_negotiated_pmts_post_object(
    request: Request,
    body: dict = Depends(object_post_params_dependency),
    focus_node=Depends(get_focus_node_post_object),
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
    url_path: str = Depends(get_unprefixed_url_path),
) -> "NegotiatedPMTs":
    from prez.services.classes import get_classes_single
    from prez.services.connegp_service import NegotiatedPMTs

    klasses_fs = await get_classes_single(URIRef(focus_node.value), repo)
    klasses = list(klasses_fs)
    params_dict = {
        "_profile": body.get("_profile", ""),
        "_mediatype": body.get("_mediatype", ""),
    }
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=params_dict,
        classes=klasses,
        listing=False,
        system_repo=system_repo,
        current_path=url_path,
    )
    await pmts.setup()
    return pmts


async def get_endpoint_structure_post_object(
    pmts: "NegotiatedPMTs" = Depends(get_negotiated_pmts_post_object),
    endpoint_uri_type: tuple = Depends(get_endpoint_uri_type),
) -> tuple:
    from prez.reference_data.prez_ns import ALTREXT

    endpoint_uri = endpoint_uri_type[0]
    if (endpoint_uri in settings.system_endpoints) or (
        pmts.selected.get("profile") == ALTREXT["alt-profile"]
    ):
        return ("profiles",)
    return settings.endpoint_structure


async def get_profile_nodeshape_post_object(
    pmts: "NegotiatedPMTs" = Depends(get_negotiated_pmts_post_object),
    focus_node=Depends(get_focus_node_post_object),
) -> "NodeShape":
    from prez.reference_data.prez_ns import ALTREXT
    from prez.cache import profiles_graph_cache
    from prez.services.query_generation.shacl import get_nodeshape
    from sparql_grammar import Var

    profile = pmts.selected.get("profile")
    if profile == ALTREXT["alt-profile"]:
        fn = Var(value="focus_node")
    else:
        fn = focus_node
    return get_nodeshape(
        uri=profile,
        graph=profiles_graph_cache,
        kind="profile",
        focus_node=fn,
    )


async def get_object_query_params_post(
    body: dict = Depends(object_post_params_dependency),
) -> ObjectQueryParams:
    params = ObjectQueryParams.__new__(ObjectQueryParams)
    params.mediatype = body.get("_mediatype")
    params.profile = body.get("_profile")
    params.facet_profile = body.get("facet_profile")
    params.subscription_key = body.get("subscription-key")
    return params


async def get_jena_fts_shacl_predicates(system_repo: Repo) -> Graph:
    query = """
    DESCRIBE ?fts_shape
    WHERE {
        { ?fts_shape a <https://prez.dev/ont/JenaFTSPropertyShape> }
        UNION
        {
            ?fts_shape a <https://prez.dev/ont/JenaFTSUnionShape> .
            ?fts_shape <http://www.w3.org/ns/shacl#union> ?u .
            ?fts_shape <http://purl.org/dc/terms/identifier> ?id .
        }
    }
    """
    return await system_repo.rdf_query_to_rdflib_graph(query)


class DummySearchMarker:
    """Marker to indicate that dummy search results should be injected."""

    pass


async def generate_search_query(
    request: Request,
    query_params: ListingQueryParams = Depends(),
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: tuple[URIRef, URIRef] = Depends(get_endpoint_uri_type),
    runtime_settings: Settings = Depends(get_runtime_settings),
):
    term = request.query_params.get("q")

    # Check for filtering/faceting parameters that allow empty search terms
    def has_filtering_params():
        params = request.query_params
        # Check for faceting
        if params.get("facet_profile"):
            return True
        # Check for CQL filter
        if params.get("filter"):
            return True
        # Check for spatial filtering
        if params.get("bbox"):
            return True
        # Check for temporal filtering
        if params.get("datetime"):
            return True
        return False

    # Check if the search term 'q' is provided
    if not term:
        # If 'q' is missing or empty, check if we're on the search endpoint
        if endpoint_uri_type[0] == EP["extended-ogc-records/search"]:
            # Allow empty search term if filtering/faceting parameters are present
            if has_filtering_params():
                if _search_uses_jena_lucene(endpoint_uri_type[0], runtime_settings):
                    filter_json = _parse_lucene_filter_json(query_params._filter, "GET")
                    search_fields = _resolve_lucene_search_fields(
                        request.query_params.getlist("fields") or None,
                        runtime_settings,
                        "GET",
                    )
                    return SearchQueryJenaLucene(
                        term=query_params.q,
                        facets=None,
                        filter_json=filter_json,
                        limit=int(query_params.limit),
                        offset=_calculate_listing_offset(query_params),
                        lucene_index_name=runtime_settings.lucene_index_name,
                        search_fields=search_fields,
                        lucene_hit_limit=_resolve_lucene_hit_limit(
                            query_params, runtime_settings
                        ),
                        order_by=query_params.order_by,
                        order_by_direction=query_params.order_by_direction,
                        include_matches=bool(query_params.q),
                        pagination_pushed_down=_lucene_uses_limit_offset_pushdown(
                            runtime_settings
                        ),
                    )
                # Return marker to indicate dummy search results needed
                return DummySearchMarker()
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Search query parameter 'q' must be provided, or use filtering parameters (facet_profile, filter, bbox, datetime).",
                )
        else:
            # For other endpoints, 'q' is optional, return None if not provided
            return None
    else:
        if _search_uses_jena_lucene(endpoint_uri_type[0], runtime_settings):
            filter_json = _parse_lucene_filter_json(query_params._filter, "GET")
            search_fields = _resolve_lucene_search_fields(
                request.query_params.getlist("fields") or None,
                runtime_settings,
                "GET",
            )
            search_query = SearchQueryJenaLucene(
                term=query_params.q,
                facets=None,
                filter_json=filter_json,
                limit=int(query_params.limit),
                offset=_calculate_listing_offset(query_params),
                lucene_index_name=runtime_settings.lucene_index_name,
                search_fields=search_fields,
                lucene_hit_limit=_resolve_lucene_hit_limit(
                    query_params, runtime_settings
                ),
                order_by=query_params.order_by,
                order_by_direction=query_params.order_by_direction,
                include_matches=bool(query_params.q),
                pagination_pushed_down=_lucene_uses_limit_offset_pushdown(
                    runtime_settings
                ),
            )
            logger.debug(f"Generated search query: {search_query}")
            return search_query

        # escaped_term = escape_for_lucene_and_sparql(term)
        predicates = request.query_params.getlist("predicates")
        page = request.query_params.get("page", 1)
        limit = request.query_params.get("limit")
        limit = int(limit) if limit else settings.search_count_limit
        offset = limit * (int(page) - 1)

        if settings.search_method == SearchMethod.DEFAULT:
            search_query = SearchQueryRegex(
                term=term,
                predicates=predicates,
                limit=limit,
                offset=offset,
            )
        elif settings.search_method == SearchMethod.FTS_FUSEKI:
            predicates = predicates if predicates else settings.search_predicates
            shacl_shapes = await get_jena_fts_shacl_predicates(system_repo)

            def _has_triple(graph: Graph, s, p, o) -> bool:
                return any(graph.triples((s, p, o)))

            shacl_shape_ids = list(
                [
                    str(x)
                    for x in shacl_shapes.objects(
                        subject=None, predicate=DCTERMS.identifier
                    )
                ]
            )
            tssp_lists = []
            tss_list = []
            non_shacl_predicates = []
            i = 100
            for pred in predicates:
                if str(pred) in shacl_shape_ids:
                    shacl_shape_uri = shacl_shapes.value(
                        subject=None, predicate=DCTERMS.identifier, object=Literal(pred)
                    )
                    if (
                        shacl_shape_uri
                        and _has_triple(
                            shacl_shapes,
                            shacl_shape_uri,
                            RDF.type,
                            ONT.JenaFTSUnionShape,
                        )
                        and _has_triple(shacl_shapes, shacl_shape_uri, SH.union, None)
                    ):
                        union_container = FTSUnionContainer(
                            uri=shacl_shape_uri,
                            graph=shacl_shapes,
                            focus_node=Var(value="focus_node"),
                            shape_number=i,
                        )
                        tssp_lists.extend(union_container.tssp_list_with_preds)
                        tss_list.extend(union_container.tss_list)
                        i = union_container.next_shape_number
                    else:
                        shacl_shape_g = shacl_shapes.cbd(shacl_shape_uri)
                        search_preds = list(
                            shacl_shape_g.objects(
                                subject=None, predicate=ONT.searchPredicate
                            )
                        )
                        ps = PropertyShape(
                            uri=shacl_shape_uri,
                            graph=shacl_shape_g,
                            kind="fts",
                            focus_node=Var(value="focus_node"),
                            shape_number=i,
                        )
                        tssp_lists.append(
                            (ps.tssp_list, search_preds, ps.focus_node_classes)
                        )
                        tss_list.extend(ps.tss_list)
                        i += 1
                else:
                    non_shacl_predicates.append(pred)

            search_query = SearchQueryFusekiFTS(
                term=term,
                non_shacl_predicates=non_shacl_predicates,
                shacl_tssp_preds=tssp_lists,
                tss_list=tss_list,
                limit=limit,
                offset=offset,
                fts_limit=settings.fts_limit,
            )
        else:
            raise NotImplementedError(
                f"Search method {settings.search_method} not implemented"
            )
        logger.debug(f"Generated search query: {search_query}")
        return search_query


async def generate_concept_hierarchy_query(
    request: Request,
    endpoint_uri_type: tuple[URIRef, URIRef] = Depends(get_endpoint_uri_type),
) -> ConceptHierarchyQuery | None:
    ep_uri = endpoint_uri_type[0]
    if ep_uri not in [OGCE["top-concepts"], OGCE["narrowers"]]:
        return None
    parent_curie = request.path_params.get("parent_curie")
    parent_uri = await get_uri_for_curie_id(parent_curie)
    child_grandchild_predicates = (
        IRI(value=SKOS["narrower"]),
        IRI(value=SKOS["broader"]),
    )
    if ep_uri == OGCE["top-concepts"]:
        parent_child_predicates = (
            IRI(value=SKOS["hasTopConcept"]),
            IRI(value=SKOS["topConceptOf"]),
        )
    else:
        parent_child_predicates = child_grandchild_predicates
    return ConceptHierarchyQuery(
        parent_uri=IRI(value=parent_uri),
        parent_child_predicates=parent_child_predicates,
        child_grandchild_predicates=child_grandchild_predicates,
    )


async def get_focus_node(
    request: Request,
    endpoint_uri_type: tuple[URIRef, URIRef] = Depends(get_endpoint_uri_type),
    url_path: str = Depends(get_unprefixed_url_path),
):
    """
    Either a variable or IRI depending on whether an object or listing endpoint is being used.
    """
    ep_uri = endpoint_uri_type[0]
    ep_type = endpoint_uri_type[1]
    if ep_uri == EP["system/object"]:
        iri = request.query_params.get("iri") or request.query_params.get("uri")
        if not iri:
            raise HTTPException(
                status_code=400,
                detail="Missing required query parameter: 'iri' or 'uri' ('uri' is marked for deprecation)",
            )
        return IRI(value=iri)
    elif ep_type == ONT.ObjectEndpoint:
        object_curie = url_path.split("/")[-1]
        focus_node_uri = await get_uri_for_curie_id(object_curie)
        return IRI(value=focus_node_uri)
    else:  # listing endpoints
        return Var(value="focus_node")


#: endpoint -> the node shape that selects focus nodes for it. These endpoints each
#: have exactly one shape, named in prez/reference_data/endpoints/endpoint_nodeshapes.ttl.
SPECIAL_CASE_NODESHAPES = {
    EP["system/object"]: URIRef("http://example.org/ns#Object"),
    EP["extended-ogc-records/top-concepts"]: URIRef(
        "http://example.org/ns#TopConcepts"
    ),
    EP["extended-ogc-records/narrowers"]: URIRef("http://example.org/ns#Narrowers"),
    EP["extended-ogc-records/cql-get"]: URIRef("http://example.org/ns#CQL"),
    EP["extended-ogc-records/search"]: URIRef("http://example.org/ns#Search"),
}


def handle_special_cases(ep_uri, focus_node):
    """
    uris provided to the nodeshapes are those in prez/reference_data/endpoints/endpoint_nodeshapes.ttl
    """
    shape_uri = SPECIAL_CASE_NODESHAPES.get(ep_uri)
    if shape_uri is None:
        return None
    return get_nodeshape(
        uri=shape_uri,
        graph=endpoints_graph_cache,
        kind="endpoint",
        focus_node=focus_node,
    )


async def get_endpoint_nodeshapes(
    request: Request,
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: tuple[URIRef, URIRef] = Depends(get_endpoint_uri_type),
    focus_node: IRI | Var = Depends(get_focus_node),
    url_path: str = Depends(get_unprefixed_url_path),
):
    """
    Determines the relevant endpoint nodeshape which will be used to list items at the endpoint.
    Complex in cases where there is one endpoint to many nodeshapes, such as the catalogs/{cat_id}/collections endpoint.
    """
    ep_uri = endpoint_uri_type[0]
    if ep_uri in [
        EP["system/object"],
        EP["extended-ogc-records/cql-get"],
        EP["extended-ogc-records/top-concepts"],
        EP["extended-ogc-records/narrowers"],
        EP["extended-ogc-records/search"],
    ]:
        return handle_special_cases(ep_uri, focus_node)

    path_node_curies = [
        i for i in url_path.split("/")[:-1] if i in request.path_params.values()
    ]
    path_nodes = {
        f"path_node_{i + 1}": IRI(value=await get_uri_for_curie_id(value))
        for i, value in enumerate(reversed(path_node_curies))
    }
    # A hierarchy level covers a listing and an item endpoint. Path segment maths is: int({2,3}/2) -> 1; int({4,5}/2) -> 2 etc.
    # For Features API mounted as "features", remove extra level when counting to get correct hierarchy level.
    hierarchy_level = int(
        len(url_path.replace("/features/collections", "/features").split("/")) / 2
    )
    """
    Determines the relevant nodeshape based on the endpoint, hierarchy level, and parent URI
    """
    node_selection_shape_uri = None
    relevant_ns_query = f"""SELECT ?ns ?tc
                            WHERE {{
                                {ep_uri.n3()} <https://prez.dev/ont/relevantShapes> ?ns .
                                ?ns <http://www.w3.org/ns/shacl#targetClass> ?tc ;
                                    <https://prez.dev/ont/hierarchyLevel> {hierarchy_level} .
                                }}"""
    _, r = await system_repo.send_queries([], [(None, relevant_ns_query)])
    tabular_results = r[0][1]
    distinct_ns = set([result["ns"]["value"] for result in tabular_results])
    if len(distinct_ns) == 1:  # only one possible node shape
        node_selection_shape_uri = URIRef(tabular_results[0]["ns"]["value"])
    elif len(distinct_ns) > 1:  # more than one possible node shape
        # try all of the available nodeshapes
        path_node_classes = {}
        for pn, uri in path_nodes.items():
            path_node_classes[pn] = await get_classes_single(URIRef(uri.value), repo)
        nodeshapes = [
            get_nodeshape(
                uri=URIRef(ns),
                graph=endpoints_graph_cache,
                kind="endpoint",
                path_nodes=path_nodes,
                focus_node=focus_node,
            )
            for ns in distinct_ns
        ]
        matching_nodeshapes = []
        for ns in nodeshapes:
            match_all_keys = True  # Assume a match for all keys initially

            for pn, klasses in path_node_classes.items():
                # Check if all classes for this path node are in the ns.classes_at_len at this pn
                if not any(klass in ns.classes_at_len.get(pn, []) for klass in klasses):
                    match_all_keys = False  # Found a key where not all classes match
                    break  # No need to check further for this ns

            if match_all_keys:
                matching_nodeshapes.append(ns)
        # TODO logic if there is more than one nodeshape - current default nodeshapes will only return one.
        if not matching_nodeshapes:
            raise ValueError(
                "No matching nodeshapes found for the given path nodes and hierarchy level"
            )
        node_selection_shape_uri = matching_nodeshapes[0].uri
    if not path_nodes:
        path_nodes = {}
    if node_selection_shape_uri:
        return get_nodeshape(
            uri=node_selection_shape_uri,
            graph=endpoints_graph_cache,
            kind="endpoint",
            path_nodes=path_nodes,
            focus_node=focus_node,
        )
    else:
        raise NoEndpointNodeshapeException(ep_uri, hierarchy_level)


async def get_negotiated_pmts(
    request: Request,
    endpoint_nodeshape: NodeShape = Depends(get_endpoint_nodeshapes),
    repo: Repo = Depends(get_data_repo),
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: URIRef = Depends(get_endpoint_uri_type),
    focus_node: IRI | Var = Depends(get_focus_node),
    url_path: str = Depends(get_unprefixed_url_path),
) -> NegotiatedPMTs:
    # Use endpoint_nodeshapes in constructing NegotiatedPMTs
    ep_type = endpoint_uri_type[1]
    if ep_type == ONT.ObjectEndpoint:
        listing = False
        klasses_fs = await get_classes_single(URIRef(focus_node.value), repo)
        klasses = list(klasses_fs)
    elif ep_type == ONT.ListingEndpoint:
        listing = True
        klasses = endpoint_nodeshape.targetClasses
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=request.query_params,
        classes=klasses,
        listing=listing,
        system_repo=system_repo,
        current_path=url_path,
    )
    await pmts.setup()
    return pmts


async def get_endpoint_structure(
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    endpoint_uri_type: URIRef = Depends(get_endpoint_uri_type),
):
    endpoint_uri = endpoint_uri_type[0]

    if (endpoint_uri in settings.system_endpoints) or (
        pmts.selected.get("profile") == ALTREXT["alt-profile"]
    ):
        return ("profiles",)
    else:
        return settings.endpoint_structure


async def get_profile_nodeshape(
    request: Request,
    pmts: NegotiatedPMTs = Depends(get_negotiated_pmts),
    endpoint_uri_type: URIRef = Depends(get_endpoint_uri_type),
    url_path: str = Depends(get_unprefixed_url_path),
):
    profile = pmts.selected.get("profile")
    if profile == ALTREXT["alt-profile"]:
        focus_node = Var(value="focus_node")
    elif endpoint_uri_type[0] == EP["system/object"]:
        # Allow 'uri' for backwards compatibility
        identifier_value = request.query_params.get("iri") or request.query_params.get(
            "uri"
        )
        if not identifier_value:
            raise HTTPException(
                status_code=400,
                detail="Missing required query parameter: 'iri' or 'uri' ('uri' is marked for deprecation)",
            )
        focus_node = IRI(value=identifier_value)
    elif endpoint_uri_type[1] == ONT.ObjectEndpoint:
        object_curie = url_path.split("/")[-1]
        focus_node_uri = await get_uri_for_curie_id(object_curie)
        focus_node = IRI(value=focus_node_uri)
    else:  # listing
        focus_node = Var(value="focus_node")
    return get_nodeshape(
        uri=profile,
        graph=profiles_graph_cache,
        kind="profile",
        focus_node=focus_node,
    )


async def get_url(
    request: Request,
):
    return request.url


async def get_endpoint_uri(
    request: Request,
):
    return URIRef(request.scope.get("route").name)


async def get_ogc_features_path_params(
    request: Request,
):
    collection_id = request.path_params.get("collectionId")
    feature_id = request.path_params.get("featureId")
    path_params = {}
    if feature_id:
        try:
            feature_uri = await get_uri_for_curie_id(feature_id)
        except ValueError:
            raise URINotFoundException(curie=feature_id)
        path_params["feature_uri"] = feature_uri
    if collection_id:
        try:
            collection_uri = await get_uri_for_curie_id(collection_id)
        except ValueError:
            raise URINotFoundException(curie=collection_id)
        path_params["collection_uri"] = collection_uri
    return path_params


async def get_ogc_features_mediatype(
    request: Request,
    endpoint_uri: URIRef = Depends(get_endpoint_uri),
):
    if endpoint_uri in [
        OGCFEAT["feature-collections"],
        OGCFEAT["feature-collection"],
        OGCFEAT["queryables-global"],
        OGCFEAT["queryables-local"],
    ]:
        allowed_mts = [
            mt.value
            for mt in [
                *AnnotatedRDFMediaType,
                *NonAnnotatedRDFMediaType,
                *SPARQLQueryMediaType,
                *JSONMediaType,
            ]
        ]
        default_mt = JSONMediaType.JSON.value
    elif endpoint_uri in [OGCFEAT["feature"], OGCFEAT["features"]]:
        allowed_mts = [
            mt.value
            for mt in [
                *AnnotatedRDFMediaType,
                *NonAnnotatedRDFMediaType,
                *SPARQLQueryMediaType,
                *GeoJSONMediaType,
            ]
        ]
        default_mt = GeoJSONMediaType.GEOJSON.value
    else:
        raise ValueError("Endpoint not recognized")

    qsa_mt = request.query_params.get("_mediatype")

    if qsa_mt:
        if qsa_mt in allowed_mts:
            return qsa_mt
    elif request.headers.get("Accept"):
        split_accept = request.headers.get("Accept").split(",")
        if any(mt in split_accept for mt in allowed_mts):
            for mt in split_accept:
                if mt in allowed_mts:
                    return mt
        else:
            return default_mt
    return default_mt


async def get_template_queries(
    endpoint_uri_type: tuple[URIRef, URIRef] = Depends(get_endpoint_uri_type),
) -> list[str] | None:
    endpoint_uri = endpoint_uri_type[0]

    template_queries = []
    # check prez_system_graph
    for s in prez_system_graph.subjects(RDF.type, ONT.TemplateQuery):
        endpoint_in_sys_graph = prez_system_graph.value(s, ONT.forEndpoint, None)
        if str(endpoint_uri) == str(endpoint_in_sys_graph):
            template_query = prez_system_graph.value(s, RDF.value, None)
            template_queries.append(str(template_query))
    if template_queries:
        return template_queries
    return None


async def check_unknown_params(request: Request):
    known_params = {
        "_mediatype",
        "_profile",
        "page",
        "limit",
        "offset",
        "facet_profile",
        "datetime",
        "bbox",
        "filter-lang",
        "filter_crs",
        "q",
        "filter",
        "order_by",
        "order_by_direction",
        "subscription-key",
        "startindex",
        "f",
    }
    unknown_params = set(request.query_params.keys()) - known_params
    if unknown_params:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown query parameters: {', '.join(unknown_params)}",
        )
