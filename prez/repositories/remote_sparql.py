import logging
from urllib.parse import quote_plus

import httpx
from rdflib import Namespace, Graph, URIRef

from prez.config import settings
from prez.repositories.base import Repo

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class RemoteSparqlRepo(Repo):
    def __init__(self, async_client: httpx.AsyncClient):
        self.async_client = async_client
        if not settings.sparql_endpoint:
            raise ValueError(
                "When using a remote SPARQL endpoint, "
                "the SPARQL_ENDPOINT setting must be set using either "
                "the environment variable or the config file."
            )

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
