import logging
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Optional, Union

import httpx
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from rdflib import Graph
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from prez.config import Settings, settings
from prez.dependencies import (
    get_annotations_store,
    get_async_http_client,
    get_oxrdflib_store,
    get_pyoxi_store,
    get_queryable_props,
    get_system_store,
    load_annotations_data_to_oxigraph,
    load_local_data_to_oxigraph,
    load_system_data_to_oxigraph,
)
from prez.exceptions.model_exceptions import (
    ClassNotFoundException,
    InvalidSPARQLQueryException,
    NoEndpointNodeshapeException,
    NoProfilesException,
    PrefixNotBoundException,
    URINotFoundException,
    MissingFilterQueryError,
)
from prez.middleware import create_validate_header_middleware
from prez.repositories import OxrdflibRepo, PyoxigraphRepo, RemoteSparqlRepo
from prez.routers.base_router import router as base_prez_router
from prez.routers.custom_endpoints import create_dynamic_router
from prez.routers.identifier import router as identifier_router
from prez.routers.management import config_router
from prez.routers.management import router as management_router
from prez.routers.ogc_features_router import features_subapi
from prez.routers.sparql import router as sparql_router
from prez.services.app_service import (
    count_objects,
    create_endpoints_graph,
    healthcheck_sparql_endpoints,
    populate_api_info,
    prefix_initialisation,
    retrieve_remote_queryable_definitions,
    retrieve_local_queryable_definitions,
    retrieve_remote_template_queries,
    retrieve_jena_fts_shapes,
)
from prez.services.exception_catchers import (
    catch_400,
    catch_404,
    catch_500,
    catch_class_not_found_exception,
    catch_httpx_error,
    catch_invalid_sparql_query,
    catch_no_endpoint_nodeshape_exception,
    catch_no_profiles_exception,
    catch_prefix_not_found_exception,
    catch_uri_not_found_exception,
    catch_missing_filter_query_param,
)
from prez.services.generate_profiles import create_profiles_graph
from prez.services.prez_logging import setup_logger


def prez_open_api_metadata(
    title: str,
    description: str,
    version: str,
    contact: Optional[Dict[str, Union[str, Any]]],
    _app: FastAPI,
):
    return get_openapi(
        title=title,
        description=description,
        version=version,
        contact=contact,
        license_info=_app.license_info,
        openapi_version=_app.openapi_version,
        terms_of_service=_app.terms_of_service,
        tags=_app.openapi_tags,
        servers=_app.servers,
        routes=_app.routes,
    )


async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logger(app.state.settings)
    log = logging.getLogger("prez")
    log.info("Starting up")

    mounted_apps = []
    # Find mounted sub-apps
    for r in app.router.routes:
        # assume all of the sub-apps do not have their own lifespan to set up their state
        if isinstance(r, Mount):
            mount_app = r.app
            if (
                isinstance(mount_app, (Starlette, FastAPI))
                and mount_app is not app
                and mount_app not in mounted_apps
            ):
                mounted_apps.append(mount_app)
    if app.state.settings.sparql_repo_type == "pyoxigraph_memory":
        app.state.pyoxi_store = pyoxi_store = get_pyoxi_store()
        for mounted_app in mounted_apps:
            mounted_app.state.pyoxi_store = pyoxi_store
        app.state.repo = repo = PyoxigraphRepo(pyoxi_store)
        await load_local_data_to_oxigraph(pyoxi_store)
    elif app.state.settings.sparql_repo_type == "pyoxigraph_persistent":
        app.state.pyoxi_store = pyoxi_store = get_pyoxi_store()
        for mounted_app in mounted_apps:
            mounted_app.state.pyoxi_store = pyoxi_store
        app.state.repo = repo = PyoxigraphRepo(pyoxi_store)
    elif app.state.settings.sparql_repo_type == "oxrdflib":
        app.state.oxrdflib_store = oxrdflib_store = get_oxrdflib_store()
        for mounted_app in mounted_apps:
            mounted_app.state.oxrdflib_store = oxrdflib_store
        app.state.repo = repo = OxrdflibRepo(oxrdflib_store)
    elif app.state.settings.sparql_repo_type == "remote":
        app.state.http_async_client = c = await get_async_http_client()
        for mounted_app in mounted_apps:
            mounted_app.state.http_async_client = c
        app.state.repo = repo = RemoteSparqlRepo(c)
        await healthcheck_sparql_endpoints()
    else:
        raise ValueError(
            "SPARQL_REPO_TYPE must be one of 'pyoxigraph_memory', 'pyoxigraph_persistent', 'oxrdflib' or 'remote'"
        )

    await prefix_initialisation(repo)
    await retrieve_remote_template_queries(repo)
    await retrieve_jena_fts_shapes(repo)
    await create_profiles_graph(repo)
    await create_endpoints_graph(app.state)
    await count_objects(repo)
    await populate_api_info()

    app.state.queryable_props = get_queryable_props()
    app.state.pyoxi_system_store = system_store = get_system_store()
    app.state.annotations_store = anno_store = get_annotations_store()

    for mounted_app in mounted_apps:
        mounted_app.state.repo = repo
        mounted_app.state.pyoxi_system_store = system_store
        mounted_app.state.annotations_store = anno_store

    await retrieve_remote_queryable_definitions(app.state, system_store)
    await retrieve_local_queryable_definitions(app.state, system_store)
    await load_system_data_to_oxigraph(system_store)
    await load_annotations_data_to_oxigraph(anno_store)

    # dynamic routes are either: custom routes if enabled, else default prez "data" routes are added dynamically
    app.include_router(create_dynamic_router())

    yield

    # Shutdown
    log.info("Shutting down...")

    # close all SPARQL async clients
    if app.state.settings.sparql_repo_type == "remote":
        await app.state.http_async_client.aclose()


def assemble_app(
    root_path: str = "",
    title: Optional[str] = None,
    description: Optional[str] = None,
    version: Optional[str] = None,
    local_settings: Optional[Settings] = None,
    **kwargs
):
    _settings = local_settings if local_settings is not None else settings
    actual_root_path = root_path or _settings.root_path or ""

    if title is None:
        title = _settings.prez_title
    if version is None:
        version = _settings.prez_version
    if description is None:
        description = _settings.prez_desc
    contact = _settings.prez_contact

    app = FastAPI(
        root_path=actual_root_path,
        title=title,
        version=version,
        description=description,
        contact=contact,
        lifespan=lifespan,
        exception_handlers={
            400: catch_400,
            404: catch_404,
            500: catch_500,
            ClassNotFoundException: catch_class_not_found_exception,
            URINotFoundException: catch_uri_not_found_exception,
            PrefixNotBoundException: catch_prefix_not_found_exception,
            NoProfilesException: catch_no_profiles_exception,
            InvalidSPARQLQueryException: catch_invalid_sparql_query,
            NoEndpointNodeshapeException: catch_no_endpoint_nodeshape_exception,
            MissingFilterQueryError: catch_missing_filter_query_param,
            httpx.HTTPError: catch_httpx_error,
        },
        **kwargs
    )

    app.state.settings = _settings

    app.include_router(management_router)
    if _settings.enable_sparql_endpoint:
        app.include_router(sparql_router)
    if _settings.configuration_mode:
        app.include_router(config_router)
        app.mount(
            "/static",
            StaticFiles(directory=Path(__file__).parent / "static"),
            name="static",
        )
    if _settings.enable_ogc_features:
        features_subapi.state.settings = _settings
        app.mount(
            _settings.ogc_features_mount_path,
            features_subapi,
        )
    app.include_router(base_prez_router)
    app.include_router(identifier_router)
    app.openapi = partial(
        prez_open_api_metadata,
        title=title,
        description=description,
        version=version,
        contact=contact,
        _app=app,
    )

    app.middleware("http")(add_cors_headers)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    validate_header_middleware = create_validate_header_middleware(
        settings.required_header
    )
    app.middleware("http")(validate_header_middleware)

    return app


def _get_sparql_service_description(request, format):
    """Return an RDF description of PROMS' read only SPARQL endpoint in a requested format
    :param rdf_fmt: 'turtle', 'n3', 'xml', 'json-ld'
    :return: string of RDF in the requested format
    """
    ttl = """
        @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix sd:     <http://www.w3.org/ns/sparql-service-description#> .
        @prefix sdf:    <http://www.w3.org/ns/formats/> .
        @prefix void:   <http://rdfs.org/ns/void#> .
        @prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
        <{0}>
            a                       sd:Service ;
            sd:endpoint             <{0}> ;
            sd:supportedLanguage    sd:SPARQL11Query ; # yes, read only, sorry!
            sd:resultFormat         sdf:SPARQL_Results_JSON ;  # yes, we only deliver JSON results, sorry!
            sd:feature sd:DereferencesURIs ;
            sd:defaultDataset [
                a sd:Dataset ;
                sd:defaultGraph [
                    a sd:Graph ;
                    void:triples "100"^^xsd:integer
                ]
            ]
        .
    """.format(
        request.url_for("sparql_get")
    )
    if format == "text/turtle":
        return dedent(ttl)
    else:
        return Graph(bind_namespaces="rdflib").parse(data=ttl).serialize(format=format)


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print(
            'Error: Uvicorn is not installed. Install it with \'poetry install --extras "server".'
        )
        import sys

        sys.exit(1)
    uvicorn.run(
        assemble_app,
        factory=True,
        port=settings.port,
        host=settings.host,
        proxy_headers=settings.proxy_headers,
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )
