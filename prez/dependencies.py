import json
from pathlib import Path

import httpx
from fastapi import Depends, Request, HTTPException
from pyoxigraph import Store
from rdflib import Dataset, URIRef, SKOS, RDF
from sparql_grammar_pydantic import IRI, Var

from prez.cache import (
    store,
    oxrdflib_store,
    system_store,
    profiles_graph_cache,
    endpoints_graph_cache,
    annotations_store,
    prez_system_graph,
    queryable_props,
)
from prez.config import settings
from prez.enums import (
    NonAnnotatedRDFMediaType,
    SPARQLQueryMediaType,
    JSONMediaType,
    GeoJSONMediaType,
)
from prez.exceptions.model_exceptions import NoEndpointNodeshapeException, URINotFoundException
from prez.enums import SearchMethod
from prez.models.query_params import QueryParams
from prez.reference_data.prez_ns import ALTREXT, ONT, EP, OGCE, OGCFEAT
from prez.repositories import PyoxigraphRepo, RemoteSparqlRepo, OxrdflibRepo, Repo
from prez.services.classes import get_classes_single
from prez.services.connegp_service import NegotiatedPMTs
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.query_generation.concept_hierarchy import ConceptHierarchyQuery
from prez.services.query_generation.cql import CQLParser
from prez.services.query_generation.search_default import SearchQueryRegex
from prez.services.query_generation.search_fts import SearchQueryFusekiFTS
from prez.services.query_generation.shacl import NodeShape
from prez.services.query_generation.sparql_escaping import escape_for_lucene_and_sparql


async def get_async_http_client():
    return httpx.AsyncClient(
        auth=(
            (settings.sparql_username, settings.sparql_password)
            if settings.sparql_username
            else None
        ),
        timeout=settings.sparql_timeout,
    )


def get_pyoxi_store():
    return store


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
    http_async_client: httpx.AsyncClient = Depends(get_async_http_client),
    pyoxi_data_store: Store = Depends(get_pyoxi_store),
    pyoxi_system_store: Store = Depends(get_system_store),
) -> Repo:
    if URIRef(request.scope.get("route").name) in settings.system_endpoints:
        return PyoxigraphRepo(pyoxi_system_store)
    if settings.sparql_repo_type == "pyoxigraph":
        return PyoxigraphRepo(pyoxi_data_store)
    elif settings.sparql_repo_type == "oxrdflib":
        return OxrdflibRepo(oxrdflib_store)
    elif settings.sparql_repo_type == "remote":
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
    for file in (Path(__file__).parent.parent / settings.local_rdf_dir).glob("*.ttl"):
        try:
            store.load(file.read_bytes(), "text/turtle")
        except SyntaxError as e:
            raise SyntaxError(f"Error parsing file {file}: {e}")


async def load_system_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    profiles_bytes = profiles_graph_cache.serialize(format="nt", encoding="utf-8")
    store.load(profiles_bytes, "application/n-triples")

    endpoints_bytes = endpoints_graph_cache.serialize(format="nt", encoding="utf-8")
    store.load(endpoints_bytes, "application/n-triples")


async def load_annotations_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    g = Dataset(default_union=True)
    for file in (Path(__file__).parent / "reference_data/annotations").glob("*"):
        g.parse(file)
    file_bytes = g.serialize(format="nt", encoding="utf-8")
    store.load(file_bytes, "application/n-triples")


async def cql_post_parser_dependency(
    request: Request,
    queryable_props: list = Depends(get_queryable_props),
) -> CQLParser:
    try:
        body = await request.json()
        context = json.load(
            (Path(__file__).parent / "reference_data/cql/default_context.json").open()
        )
        cql_parser = CQLParser(
            cql=body, context=context, queryable_props=queryable_props
        )
        cql_parser.generate_jsonld()
        cql_parser.parse()
        return cql_parser
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")
    except Exception as e:  # Replace with your specific parsing exception
        raise HTTPException(
            status_code=400, detail=e.args[0] if e.args else "Error parsing CQL."
        )


async def cql_get_parser_dependency(
    query_params: QueryParams = Depends(),
    queryable_props: list = Depends(get_queryable_props),
) -> CQLParser:
    if query_params.filter:
        try:
            crs = query_params.filter_crs
            query = json.loads(query_params.filter)
            context = json.load(
                (
                    Path(__file__).parent / "reference_data/cql/default_context.json"
                ).open()
            )
            cql_parser = CQLParser(
                cql=query, context=context, crs=crs, queryable_props=queryable_props
            )
            cql_parser.generate_jsonld()
            cql_parser.parse()
            return cql_parser
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format.")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="Invalid CQL format: Parsing failed."
            )


async def generate_search_query(request: Request):
    term = request.query_params.get("q")
    if term:
        escaped_term = escape_for_lucene_and_sparql(term)
        predicates = request.query_params.getlist("predicates")
        page = request.query_params.get("page", 1)
        limit = request.query_params.get("limit")
        limit = int(limit) if limit else settings.search_count_limit
        offset = limit * (int(page) - 1)

        if settings.search_method == SearchMethod.DEFAULT:
            return SearchQueryRegex(
                term=escaped_term,
                predicates=predicates,
                limit=limit,
                offset=offset,
            )
        elif settings.search_method == SearchMethod.FTS_FUSEKI:
            return SearchQueryFusekiFTS(
                term=escaped_term, predicates=predicates, limit=limit, offset=offset
            )
        else:
            raise NotImplementedError(
                f"Search method {settings.search_method} not implemented"
            )


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
):
    """
    Either a variable or IRI depending on whether an object or listing endpoint is being used.
    """
    ep_uri = endpoint_uri_type[0]
    ep_type = endpoint_uri_type[1]
    if ep_uri == EP["system/object"]:
        uri = request.query_params.get("uri")
        return IRI(value=uri)
    elif ep_type == ONT.ObjectEndpoint:
        object_curie = request.url.path.split("/")[-1]
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
        i for i in request.url.path.split("/")[:-1] if i in request.path_params.values()
    ]
    path_nodes = {
        f"path_node_{i + 1}": IRI(value=await get_uri_for_curie_id(value))
        for i, value in enumerate(reversed(path_node_curies))
    }
    hierarchy_level = int(len(request.url.path.split("/")) / 2)
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
        current_path=request.url.path,
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
):
    profile = pmts.selected.get("profile")
    if profile == ALTREXT["alt-profile"]:
        focus_node = Var(value="focus_node")
    elif endpoint_uri_type[0] == EP["system/object"]:
        uri = request.query_params.get("uri")
        focus_node = IRI(value=uri)
    elif endpoint_uri_type[1] == ONT.ObjectEndpoint:
        object_curie = request.url.path.split("/")[-1]
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
            for mt in [*NonAnnotatedRDFMediaType, *SPARQLQueryMediaType, *JSONMediaType]
        ]
        default_mt = JSONMediaType.JSON.value
    elif endpoint_uri in [OGCFEAT["feature"], OGCFEAT["features"]]:
        allowed_mts = [
            mt.value
            for mt in [
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


async def get_template_query(
    endpoint_uri_type: tuple[URIRef, URIRef] = Depends(get_endpoint_uri_type),
):
    endpoint_uri = endpoint_uri_type[0]
    filename = settings.endpoint_to_template_query_filename.get(str(endpoint_uri))

    # check local files
    if filename:
        return (
            Path(__file__).parent / "reference_data/template_queries" / filename
        ).read_text()

    # check prez_system_graph
    for s in prez_system_graph.subjects(RDF.type, ONT.TemplateQuery):
        endpoint_in_sys_graph = prez_system_graph.value(s, ONT.forEndpoint, None)
        if str(endpoint_uri) == str(endpoint_in_sys_graph):
            template_query = prez_system_graph.value(s, RDF.value, None)
            return str(template_query)
    return None


async def check_unknown_params(request: Request):
    known_params = {
        "_mediatype",
        "page",
        "limit",
        "datetime",
        "bbox",
        "filter-lang",
        "filter_crs",
        "q",
        "filter",
        "order_by",
        "order_by_direction",
    }
    unknown_params = set(request.query_params.keys()) - known_params
    if unknown_params:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown query parameters: {', '.join(unknown_params)}",
        )
