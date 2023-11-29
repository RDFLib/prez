from pathlib import Path

import httpx
from fastapi import Depends
from pyoxigraph import Store

from prez.cache import store, oxrdflib_store, system_store, profiles_graph_cache
from prez.config import settings
from prez.sparql.methods import PyoxigraphRepo, RemoteSparqlRepo, OxrdflibRepo


async def get_async_http_client():
    return httpx.AsyncClient(
        auth=(settings.sparql_username, settings.sparql_password)
        if settings.sparql_username
        else None,
        timeout=settings.sparql_timeout,
    )


def get_pyoxi_store():
    return store


def get_system_store():
    return system_store


def get_oxrdflib_store():
    return oxrdflib_store


async def get_repo(
    http_async_client: httpx.AsyncClient = Depends(get_async_http_client),
    pyoxi_store: Store = Depends(get_pyoxi_store),
):
    if settings.sparql_repo_type == "pyoxigraph":
        return PyoxigraphRepo(pyoxi_store)
    elif settings.sparql_repo_type == "oxrdflib":
        return OxrdflibRepo(oxrdflib_store)
    elif settings.sparql_repo_type == "remote":
        return RemoteSparqlRepo(http_async_client)


async def get_system_repo(
    pyoxi_store: Store = Depends(get_system_store),
):
    """
    A pyoxigraph Store with Prez system data including:
    - Profiles
    # TODO add and test other system data (endpoints etc.)
    """
    return PyoxigraphRepo(pyoxi_store)


async def load_local_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    for file in (Path(__file__).parent.parent / "rdf").glob("*.ttl"):
        store.load(file.read_bytes(), "text/turtle")


async def load_profile_data_to_oxigraph(store: Store):
    """
    Loads all the data from the local data directory into the local SPARQL endpoint
    """
    # TODO refactor to use the local files directly
    graph_bytes = profiles_graph_cache.serialize(format="nt", encoding="utf-8")
    store.load(graph_bytes, "application/n-triples")
