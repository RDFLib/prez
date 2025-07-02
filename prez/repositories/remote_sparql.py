from io import BytesIO
import logging
from typing import Any
from urllib.parse import quote_plus

import httpx
from pyoxigraph import RdfFormat, Store
from rdflib import Graph, Namespace, URIRef

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

    async def _send_query(self, query: str, mediatype="text/turtle") -> httpx.Response:
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

    async def rdf_query_to_rdflib_graph(
        self, query: str, into_graph: Graph | None = None
    ) -> Graph:
        """
        Sends a SPARQL query asynchronously and parses the response into an RDFLib Graph.
        Args: query: str: A SPARQL query to be sent asynchronously.
        Returns: rdflib.Graph: An RDFLib Graph object
        """
        response: httpx.Response = await self._send_query(query)
        response_format = response.headers.get("content-type", "application/n-triples")
        response_format = response_format.split(";")[
            0
        ]  # handle cases like 'application/n-triples;charset=UTF-8' from GraphDB
        if into_graph is not None:
            g = into_graph
        else:
            g = Graph()
        content_bytes = await response.aread()
        return g.parse(data=content_bytes, format=response_format)

    async def rdf_query_to_pyoxigraph_store(
        self, query: str, into_store: Store | None = None
    ) -> Store:
        """
        Sends a SPARQL query asynchronously and parses the response into a PyOxigraph Store.
        Args: query: str: A SPARQL query to be sent asynchronously.
        Returns: pyoxigraph.Store: An pyoxigraph Store object
        """
        response: httpx.Response = await self._send_query(query)
        response_format = response.headers.get("content-type", "application/n-triples")
        response_format = response_format.split(";")[
            0
        ]  # handle cases like 'application/n-triples;charset=UTF-8' from GraphDB
        if into_store is not None:
            s = into_store
        else:
            s = Store()
        content_bytes = await response.aread()
        oxigraph_format = sparql_response_mimetype_to_oxigraph_format(response_format)
        s.bulk_load(content_bytes, oxigraph_format)
        return s

    async def tabular_query_to_table(
        self, query: str, context: URIRef | None = None
    ) -> tuple[URIRef | None, list[dict[str, Any]]]:
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
        """Sends a request (containing a SPARQL query in the URL parameters) to a proxied SPARQL endpoint."""
        # Convert raw_headers to a dict, excluding the 'host' header
        headers = {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in raw_headers
            if k.lower() != b"host"
        }

        if method == "GET":
            query_escaped = quote_plus(query)
            url = f"{settings.sparql_endpoint}?query={query_escaped}"
            request = httpx.Request(method, url, headers=headers)
        else:
            url = settings.sparql_endpoint
            # Prepare form data
            form_data = f"query={quote_plus(query)}"

            # Set correct headers for form data
            headers["content-type"] = "application/x-www-form-urlencoded"
            headers["content-length"] = str(len(form_data))

            request = httpx.Request(
                method, url, headers=headers, content=form_data.encode("utf-8")
            )

        # Add the correct 'host' header
        request.headers["host"] = httpx.URL(url).host

        response = await self.async_client.send(request, stream=True)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await response.aread()
            print(f"Error content: {response.text}")
            raise httpx.HTTPStatusError(
                f"HTTP Error {response.status_code}: {response.text}",
                request=request,
                response=response,
            ) from e

        return response


def sparql_response_mimetype_to_oxigraph_format(mimetype: str) -> RdfFormat:
    """Converts a SPARQL response mimetype to an Oxigraph RdfFormat."""
    if mimetype == "application/n-triples":
        return RdfFormat.N_TRIPLES
    elif mimetype == "application/rdf+xml":
        return RdfFormat.RDF_XML
    elif mimetype == "text/turtle":
        return RdfFormat.TURTLE
    elif mimetype == "application/ld+json":
        return RdfFormat.JSON_LD
    elif mimetype == "turtle" or mimetype == "ttl":
        return RdfFormat.TURTLE
    elif mimetype == "xml" or mimetype == "application/xml":
        return RdfFormat.RDF_XML
    elif mimetype == "application/json" or mimetype == "json":
        return RdfFormat.JSON_LD
    elif mimetype == "ntriples" or mimetype == "nt":
        return RdfFormat.N_TRIPLES
    else:
        raise ValueError(f"Unsupported SPARQL response mimetype: {mimetype}")
