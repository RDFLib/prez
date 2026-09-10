import hashlib
import logging
import time
from typing import Any
from urllib.parse import quote_plus

import httpx
from pyoxigraph import RdfFormat, Store
from rdflib import Graph, Namespace, URIRef

from prez.config import settings
from prez.repositories.base import Repo
from prez.services.connegp_service import OXIGRAPH_SERIALIZER_TYPES_MAP
from prez.services.timing_csv import log_timing_csv

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


def _query_fingerprint(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]


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
        data = {"query": query}
        if settings.sparql_timeout_param_name:
            data[settings.sparql_timeout_param_name] = str(settings.sparql_timeout)

        query_rq = self.async_client.build_request(
            "POST",
            url=settings.sparql_endpoint,
            headers={"Accept": mediatype},
            data=data,
        )
        query_id = _query_fingerprint(query)
        t0 = time.perf_counter()
        try:
            response = await self.async_client.send(query_rq, stream=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            log.debug(
                "remote_sparql send_complete query_id=%s accept=%s status=%s elapsed_ms=%.1f endpoint=%s",
                query_id,
                mediatype,
                response.status_code,
                elapsed_ms,
                settings.sparql_endpoint,
            )
            # A failing status is raised here, with the endpoint's own error text read
            # into the message rather than a bare "Bad Request" (#447).
            await self._raise_for_status_with_body(response)
            return response
        except httpx.TimeoutException as e:
            timeout_msg = (
                f"SPARQL query timed out after {settings.sparql_timeout} seconds"
            )
            if settings.sparql_timeout_param_name:
                timeout_msg += f" (sent '{settings.sparql_timeout_param_name}={settings.sparql_timeout}' to remote endpoint)"
            log.error(timeout_msg)
            raise httpx.TimeoutException(timeout_msg) from e

    async def _raise_for_status_with_body(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            content_bytes = await response.aread()
            body_text = content_bytes.decode("utf-8", errors="replace")
            raise httpx.HTTPStatusError(
                f"HTTP Error {response.status_code}: {body_text}",
                request=response.request,
                response=response,
            ) from e

    async def rdf_query_to_rdflib_graph(
        self, query: str, into_graph: Graph | None = None
    ) -> Graph:
        """
        Sends a SPARQL query asynchronously and parses the response into an RDFLib Graph.
        Args: query: str: A SPARQL query to be sent asynchronously.
        Returns: rdflib.Graph: An RDFLib Graph object
        """
        query_id = _query_fingerprint(query)
        total_start = time.perf_counter()
        response: httpx.Response = await self._send_query(query)
        response_format = response.headers.get("content-type", "application/n-triples")
        response_format = response_format.split(";")[
            0
        ]  # handle cases like 'application/n-triples;charset=UTF-8' from GraphDB
        if into_graph is not None:
            g = into_graph
        else:
            g = Graph()
        read_start = time.perf_counter()
        content_bytes = await response.aread()
        read_ms = (time.perf_counter() - read_start) * 1000
        parse_start = time.perf_counter()
        parsed = g.parse(data=content_bytes, format=response_format)
        parse_ms = (time.perf_counter() - parse_start) * 1000
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "remote_sparql rdflib_graph query_id=%s format=%s bytes=%s read_ms=%.1f parse_ms=%.1f total_ms=%.1f",
            query_id,
            response_format,
            len(content_bytes),
            read_ms,
            parse_ms,
            total_ms,
        )
        return parsed

    async def rdf_query_to_oxigraph_store(
        self, query: str, into_store: Store | None = None
    ) -> Store:
        """
        Sends a SPARQL query asynchronously and parses the response into a PyOxigraph Store.
        Args: query: str: A SPARQL query to be sent asynchronously.
        Returns: pyoxigraph.Store: An pyoxigraph Store object
        """
        query_id = _query_fingerprint(query)
        total_start = time.perf_counter()
        response: httpx.Response = await self._send_query(query)
        response_format = response.headers.get("content-type", "application/n-triples")
        response_format = response_format.split(";")[
            0
        ]  # handle cases like 'application/n-triples;charset=UTF-8' from GraphDB
        if into_store is not None:
            s = into_store
        else:
            s = Store()
        read_start = time.perf_counter()
        content_bytes = await response.aread()
        read_ms = (time.perf_counter() - read_start) * 1000
        oxigraph_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(
            response_format, RdfFormat.N_TRIPLES
        )
        bulk_load_start = time.perf_counter()
        s.bulk_load(content_bytes, oxigraph_format)
        bulk_load_ms = (time.perf_counter() - bulk_load_start) * 1000
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "remote_sparql oxigraph_store query_id=%s format=%s oxigraph_format=%s bytes=%s read_ms=%.1f bulk_load_ms=%.1f total_ms=%.1f",
            query_id,
            response_format,
            oxigraph_format,
            len(content_bytes),
            read_ms,
            bulk_load_ms,
            total_ms,
        )
        log_timing_csv(
            "remote_sparql_oxigraph_store",
            query_id=query_id,
            format=response_format,
            oxigraph_format=str(oxigraph_format),
            bytes=len(content_bytes),
            read_ms=f"{read_ms:.1f}",
            bulk_load_ms=f"{bulk_load_ms:.1f}",
            total_ms=f"{total_ms:.1f}",
        )
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
        query_id = _query_fingerprint(query)
        read_start = time.perf_counter()
        await response.aread()
        read_ms = (time.perf_counter() - read_start) * 1000
        log.debug(
            "remote_sparql tabular_query query_id=%s status=%s read_ms=%.1f",
            query_id,
            response.status_code,
            read_ms,
        )
        log_timing_csv(
            "remote_sparql_tabular_query",
            query_id=query_id,
            status=response.status_code,
            read_ms=f"{read_ms:.1f}",
        )
        return context, response.json()["results"]["bindings"]

    async def sparql(
        self, query: str, raw_headers: list[tuple[bytes, bytes]], method: str = "GET"
    ):
        """Sends a request (containing a SPARQL query in the URL parameters) to a proxied SPARQL endpoint."""
        query_id = _query_fingerprint(query)
        total_start = time.perf_counter()
        # Convert raw_headers to a dict, excluding the 'host' header
        headers = {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in raw_headers
            if k.lower() != b"host"
        }

        if method == "GET":
            query_escaped = quote_plus(query)
            url = f"{settings.sparql_endpoint}?query={query_escaped}"
            if settings.sparql_timeout_param_name:
                url += (
                    f"&{settings.sparql_timeout_param_name}={settings.sparql_timeout}"
                )
            request = httpx.Request(method, url, headers=headers)
        else:
            url = settings.sparql_endpoint
            # Prepare form data
            form_data = f"query={quote_plus(query)}"
            if settings.sparql_timeout_param_name:
                form_data += (
                    f"&{settings.sparql_timeout_param_name}={settings.sparql_timeout}"
                )

            # Set correct headers for form data
            headers["content-type"] = "application/x-www-form-urlencoded"
            headers["content-length"] = str(len(form_data))

            request = httpx.Request(
                method, url, headers=headers, content=form_data.encode("utf-8")
            )

        # Add the correct 'host' header
        request.headers["host"] = httpx.URL(url).host

        send_start = time.perf_counter()
        response = await self.async_client.send(request, stream=True)
        send_ms = (time.perf_counter() - send_start) * 1000
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
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "remote_sparql proxy query_id=%s method=%s status=%s send_ms=%.1f total_ms=%.1f endpoint=%s",
            query_id,
            method,
            response.status_code,
            send_ms,
            total_ms,
            settings.sparql_endpoint,
        )
        log_timing_csv(
            "remote_sparql_proxy",
            query_id=query_id,
            method=method,
            status=response.status_code,
            endpoint=settings.sparql_endpoint,
            elapsed_ms=f"{send_ms:.1f}",
            total_ms=f"{total_ms:.1f}",
        )

        return response
