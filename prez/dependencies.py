import json
import logging
from pathlib import Path

import httpx
from fastapi import Depends, HTTPException, Request
from pyoxigraph import Store, RdfFormat, DefaultGraph as OxiDefaultGraph
from rdflib import DCTERMS, RDF, SKOS, Dataset, Literal, URIRef, Graph
from sparql_grammar_pydantic import IRI, Var

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
from prez.config import settings
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
from prez.models.query_params import ListingQueryParams
from prez.reference_data.prez_ns import ALTREXT, EP, OGCE, OGCFEAT, ONT
from prez.repositories import OxrdflibRepo, PyoxigraphRepo, RemoteSparqlRepo, Repo
from prez.services.classes import get_classes_single
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.search_default import SearchQueryRegex
from prez.services.query_generation.search_fuseki_fts import SearchQueryFusekiFTS
from prez.services.query_generation.shacl import NodeShape, PropertyShape

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
    if settings.sparql_repo_type == "pyoxigraph_memory" or settings.sparql_repo_type == "pyoxigraph_persistent":
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


async def load_local_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    default = OxiDefaultGraph()
    for file in (Path(__file__).parent.parent / settings.pyoxigraph_data_dir).glob("**/*.ttl"):
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
    for file in (Path(__file__).parent / "reference_data/annotations").glob("*.nt"):
        store.bulk_load(None, RdfFormat.N_TRIPLES, path=str(file), to_graph=default)
    for file in (Path(__file__).parent / "reference_data/annotations").glob("*.ttl"):
        store.bulk_load(None, RdfFormat.TURTLE, path=str(file), to_graph=default)
    for file in (Path(__file__).parent / "reference_data/annotations").glob("*.nq"):
        store.bulk_load(None, RdfFormat.N_QUADS, path=str(file))
    for file in (Path(__file__).parent / "reference_data/annotations").glob("*.trig"):
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
    try:
        body = await request.json()
        cql_parser = CQLParser(cql=body, queryable_props=queryable_props)
        cql_parser.generate_jsonld()
        try:
            cql_parser.parse()
        except Exception as e:
            raise (e.args[0] if e.args else "Error parsing CQL.")
        return cql_parser
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")
    except Exception as e:  # Replace with your specific parsing exception
        raise HTTPException(
            status_code=400, detail=e.args[0] if e.args else "Error parsing CQL."
        )


async def cql_get_parser_dependency(
    query_params: ListingQueryParams = Depends(),
    queryable_props: list = Depends(get_queryable_props),
    endpoint_uri_type: str = Depends(get_endpoint_uri_type),
) -> CQLParser:
    if query_params._filter:
        try:
            crs = query_params.filter_crs
            query = json.loads(query_params._filter)
            cql_parser = CQLParser(cql=query, crs=crs, queryable_props=queryable_props)
            cql_parser.generate_jsonld()
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


async def get_jena_fts_shacl_predicates(system_repo: Repo) -> Graph:
    query = "DESCRIBE ?fts_shape WHERE {?fts_shape a <https://prez.dev/ont/JenaFTSPropertyShape>}"
    return await system_repo.rdf_query_to_rdflib_graph(query)


async def generate_search_query(
    request: Request,
    system_repo: Repo = Depends(get_system_repo),
    endpoint_uri_type: tuple[URIRef, URIRef] = Depends(get_endpoint_uri_type),
):
    term = request.query_params.get("q")
    # Check if the search term 'q' is provided
    if not term:
        # If 'q' is missing or empty, only raise error if it's the search endpoint
        if endpoint_uri_type[0] == EP["extended-ogc-records/search"]:
            raise HTTPException(
                status_code=400,
                detail="Search query parameter 'q' must be provided.",
            )
        else:
            # For other endpoints, 'q' is optional, return None if not provided
            return None
    else:
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
                    tssp_lists.append((ps.tssp_list, search_preds))
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


async def get_unprefixed_url_path(
    request: Request,
) -> str:
    root_path = request.scope.get("app_root_path", request.scope.get("root_path", ""))
    return request.url.path[len(root_path) :]


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


def handle_special_cases(ep_uri, focus_node):
    """
    uris provided to the nodeshapes are those in prez/reference_data/endpoints/endpoint_nodeshapes.ttl
    """
    if ep_uri == EP["system/object"]:
        return NodeShape(
            uri=URIRef("http://example.org/ns#Object"),
            graph=endpoints_graph_cache,
            kind="endpoint",
            focus_node=focus_node,
        )
    elif ep_uri == EP["extended-ogc-records/top-concepts"]:
        return NodeShape(
            uri=URIRef("http://example.org/ns#TopConcepts"),
            graph=endpoints_graph_cache,
            kind="endpoint",
            focus_node=focus_node,
        )
    elif ep_uri == EP["extended-ogc-records/narrowers"]:
        return NodeShape(
            uri=URIRef("http://example.org/ns#Narrowers"),
            graph=endpoints_graph_cache,
            kind="endpoint",
            focus_node=focus_node,
        )
    elif ep_uri == EP["extended-ogc-records/cql-get"]:
        return NodeShape(
            uri=URIRef("http://example.org/ns#CQL"),
            graph=endpoints_graph_cache,
            kind="endpoint",
            focus_node=focus_node,
        )
    elif ep_uri == EP["extended-ogc-records/search"]:
        return NodeShape(
            uri=URIRef("http://example.org/ns#Search"),
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
            NodeShape(
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
        ns = NodeShape(
            uri=node_selection_shape_uri,
            graph=endpoints_graph_cache,
            kind="endpoint",
            path_nodes=path_nodes,
            focus_node=focus_node,
        )
        return ns
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
    return NodeShape(
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
