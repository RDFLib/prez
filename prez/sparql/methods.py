import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List
from typing import Tuple
from urllib.parse import quote_plus

import httpx
import pyoxigraph
from fastapi.concurrency import run_in_threadpool
from rdflib import Namespace, Graph, URIRef, Literal, BNode

from prez.config import settings

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class Repo(ABC):
    @abstractmethod
    async def rdf_query_to_graph(self, query: str):
        pass

    @abstractmethod
    async def tabular_query_to_table(self, query: str, context: URIRef = None):
        pass

    async def send_queries(
        self, rdf_queries: List[str], tabular_queries: List[Tuple[URIRef, str]] = None
    ):
        # Common logic to send both query types in parallel
        results = await asyncio.gather(
            *[self.rdf_query_to_graph(query) for query in rdf_queries if query],
            *[
                self.tabular_query_to_table(query, context)
                for context, query in tabular_queries
                if query
            ],
        )
        g = Graph()
        tabular_results = []
        for result in results:
            if isinstance(result, Graph):
                g += result
            else:
                tabular_results.append(result)
        return g, tabular_results


class RemoteSparqlRepo(Repo):
    def __init__(self, async_client: httpx.AsyncClient):
        self.async_client = async_client

    async def _send_query(self, query: str, mediatype="text/turtle"):
        """Sends a SPARQL query asynchronously.
        Args: query: str: A SPARQL query to be sent asynchronously.
        Returns: httpx.Response: A httpx.Response object
        """
        query_rq = self.async_client.build_request(
            "POST",
            url=settings.sparql_endpoint,
            headers={"Accept": mediatype},
            data={"query": query},
        )
        response = await self.async_client.send(query_rq, stream=True)
        return response

    async def rdf_query_to_graph(self, query: str) -> Graph:
        """
        Sends a SPARQL query asynchronously and parses the response into an RDFLib Graph.
        Args: query: str: A SPARQL query to be sent asynchronously.
        Returns: rdflib.Graph: An RDFLib Graph object
        """
        response = await self._send_query(query)
        g = Graph()
        await response.aread()
        return g.parse(data=response.text, format="turtle")

    async def tabular_query_to_table(self, query: str, context: URIRef = None):
        """
        Sends a SPARQL query asynchronously and parses the response into a table format.
        The optional context parameter allows an identifier to be supplied with the query, such that multiple results can be
        distinguished from each other.
        """
        response = await self._send_query(query, "application/sparql-results+json")
        await response.aread()
        return context, response.json()["results"]["bindings"]

    async def sparql(
        self, query: str, raw_headers: list[tuple[bytes, bytes]], method: str = "GET"
    ):
        """Sends a starlette Request object (containing a SPARQL query in the URL parameters) to a proxied SPARQL
        endpoint."""
        # TODO: This only supports SPARQL GET requests because the query is sent as a query parameter.

        query_escaped_as_bytes = f"query={quote_plus(query)}".encode("utf-8")

        # TODO: Global app settings should be passed in as a function argument.
        url = httpx.URL(url=settings.sparql_endpoint, query=query_escaped_as_bytes)
        headers = []
        for header in raw_headers:
            if header[0] != b"host":
                headers.append(header)
        headers.append((b"host", str(url.host).encode("utf-8")))
        rp_req = self.async_client.build_request(method, url, headers=headers)
        return await self.async_client.send(rp_req, stream=True)


class PyoxigraphRepo(Repo):
    def __init__(self, pyoxi_store: pyoxigraph.Store):
        self.pyoxi_store = pyoxi_store

    def _sync_rdf_query_to_graph(self, query: str) -> Graph:
        results = self.pyoxi_store.query(query)
        ntriples = " .\n".join([str(r) for r in list(results)]) + " ."
        g = Graph()
        g.bind("prez", URIRef("https://prez.dev/"))
        if ntriples == " .":
            return g
        return g.parse(data=ntriples, format="ntriples")

    def _sync_tabular_query_to_table(self, query: str, context: URIRef = None):
        results = self.pyoxi_store.query(query)
        variables = results.variables
        results_list = []
        for result in results:
            results_dict = {}
            for var in variables:
                binding = result[var]
                if binding:
                    binding_type = self._pyoxi_result_type(binding)
                    results_dict[str(var)[1:]] = {
                        "type": binding_type,
                        "value": binding.value,
                    }
            results_list.append(results_dict)
        return context, results_list

    async def rdf_query_to_graph(self, query: str) -> Graph:
        return await run_in_threadpool(self._sync_rdf_query_to_graph, query)

    async def tabular_query_to_table(self, query: str, context: URIRef = None):
        return await run_in_threadpool(
            self._sync_tabular_query_to_table, query, context
        )

    @staticmethod
    def _pyoxi_result_type(term) -> str:
        if isinstance(term, pyoxigraph.Literal):
            return "literal"
        elif isinstance(term, pyoxigraph.NamedNode):
            return "uri"
        elif isinstance(term, pyoxigraph.BlankNode):
            return "bnode"
        else:
            raise ValueError(f"Unknown type: {type(term)}")


class OxrdflibRepo(Repo):
    def __init__(self, oxrdflib_graph: Graph):
        self.oxrdflib_graph = oxrdflib_graph

    def _sync_rdf_query_to_graph(self, query: str) -> Graph:
        results = self.oxrdflib_graph.query(query)
        return results.graph

    def _sync_tabular_query_to_table(self, query: str, context: URIRef = None):
        results = self.oxrdflib_graph.query(query)
        reformatted_results = []
        for result in results:
            reformatted_result = {}
            for var in results.vars:
                binding = result[var]
                if binding:
                    str_type = self._str_type_for_rdflib_type(binding)
                    reformatted_result[str(var)] = {"type": str_type, "value": binding}
            reformatted_results.append(reformatted_result)
        return context, reformatted_results

    async def rdf_query_to_graph(self, query: str) -> Graph:
        return await run_in_threadpool(self._sync_rdf_query_to_graph, query)

    async def tabular_query_to_table(self, query: str, context: URIRef = None):
        return await run_in_threadpool(
            self._sync_tabular_query_to_table, query, context
        )

    def _str_type_for_rdflib_type(self, instance):
        map = {URIRef: "uri", BNode: "bnode", Literal: "literal"}
        return map[type(instance)]
