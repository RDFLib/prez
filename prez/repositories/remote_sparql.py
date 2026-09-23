import hashlib
import time
from typing import Any
from urllib.parse import quote_plus, urlsplit, urlunsplit

import httpx
from pyoxigraph import RdfFormat, Store
from rdflib import Graph, Namespace, URIRef

from prez.config import settings
from prez.repositories.base import Repo
from prez.services.connegp_service import OXIGRAPH_SERIALIZER_TYPES_MAP
from prez.services.prez_logging import get_logger, record_downstream_timing

PREZ = Namespace("https://prez.dev/")


log = get_logger(__name__)


def _query_fingerprint(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]


def _safe_endpoint(endpoint: str) -> str:
    """Return endpoint metadata without credentials, query parameters, or fragments."""
    parsed = urlsplit(endpoint)
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError:
        port = ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, "", ""))


class _TimedSparqlStream(httpx.AsyncByteStream):
    """Track time awaiting response body chunks from the SPARQL endpoint."""

    def __init__(self, stream: httpx.AsyncByteStream):
        self._stream = stream

    async def __aiter__(self):
        iterator = self._stream.__aiter__()
        while True:
            started_at = time.perf_counter()
            try:
                chunk = await anext(iterator)
            except StopAsyncIteration:
                record_downstream_timing(started_at, time.perf_counter())
                return
            record_downstream_timing(started_at, time.perf_counter())
            yield chunk

    async def aclose(self) -> None:
        await self._stream.aclose()


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

        headers = {"Accept": mediatype}
        query_rq = self.async_client.build_request(
            "POST",
            url=settings.sparql_endpoint,
            headers=headers,
            data=data,
        )
        query_id = _query_fingerprint(query)
        t0 = time.perf_counter()
        try:
            response = await self.async_client.send(query_rq, stream=True)
            response_stream = getattr(response, "stream", None)
            if isinstance(response_stream, httpx.AsyncByteStream):
                response.stream = _TimedSparqlStream(response_stream)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            log.debug(
                "Remote SPARQL request completed",
                extra={
                    "event.name": "remote_sparql.send_complete",
                    "prez.sparql.query_fingerprint": query_id,
                    "prez.repository.type": "remote",
                    "http.request.header.accept": mediatype,
                    "http.response.status_code": response.status_code,
                    "duration_ms": round(elapsed_ms, 1),
                    "prez.sparql.endpoint": _safe_endpoint(settings.sparql_endpoint),
                },
            )
            # Read error responses before raising so the exception handler can return
            # the endpoint detail without embedding that potentially sensitive,
            # unbounded body in the exception message or a later traceback.
            await self._raise_for_status_with_body(response, query_id)
            return response
        except httpx.TimeoutException as e:
            timeout_msg = (
                f"SPARQL query timed out after {settings.sparql_timeout} seconds"
            )
            if settings.sparql_timeout_param_name:
                timeout_msg += f" (sent '{settings.sparql_timeout_param_name}={settings.sparql_timeout}' to remote endpoint)"
            log.error(
                "Remote SPARQL request timed out",
                extra={
                    "event.name": "remote_sparql.timeout",
                    "prez.sparql.query_fingerprint": query_id,
                    "prez.repository.type": "remote",
                    "prez.sparql.endpoint": _safe_endpoint(settings.sparql_endpoint),
                    "timeout_seconds": settings.sparql_timeout,
                },
            )
            raise httpx.TimeoutException(timeout_msg) from e
        finally:
            record_downstream_timing(t0, time.perf_counter())

    async def _raise_for_status_with_body(
        self, response: httpx.Response, query_fingerprint: str
    ) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            content_bytes = await response.aread()
            log.error(
                "Remote SPARQL request failed",
                extra={
                    "event.name": "remote_sparql.error",
                    "prez.sparql.query_fingerprint": query_fingerprint,
                    "prez.repository.type": "remote",
                    "http.response.status_code": response.status_code,
                    "response_size_bytes": len(content_bytes),
                    "prez.sparql.endpoint": _safe_endpoint(settings.sparql_endpoint),
                },
            )
            raise httpx.HTTPStatusError(
                f"Remote SPARQL endpoint returned HTTP {response.status_code}",
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
        read_end = time.perf_counter()
        record_downstream_timing(read_start, read_end)
        read_ms = (read_end - read_start) * 1000
        parse_start = time.perf_counter()
        parsed = g.parse(data=content_bytes, format=response_format)
        parse_ms = (time.perf_counter() - parse_start) * 1000
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "Remote SPARQL RDF graph parsed",
            extra={
                "event.name": "remote_sparql.rdflib_graph",
                "prez.sparql.query_fingerprint": query_id,
                "prez.repository.type": "remote",
                "http.response.header.content-type": response_format,
                "response_size_bytes": len(content_bytes),
                "remote_read_duration_ms": round(read_ms, 1),
                "parse_duration_ms": round(parse_ms, 1),
                "duration_ms": round(total_ms, 1),
            },
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
        read_end = time.perf_counter()
        record_downstream_timing(read_start, read_end)
        read_ms = (read_end - read_start) * 1000
        oxigraph_format = OXIGRAPH_SERIALIZER_TYPES_MAP.get(
            response_format, RdfFormat.N_TRIPLES
        )
        bulk_load_start = time.perf_counter()
        s.bulk_load(content_bytes, oxigraph_format)
        bulk_load_ms = (time.perf_counter() - bulk_load_start) * 1000
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "Remote SPARQL results loaded into Oxigraph",
            extra={
                "event.name": "remote_sparql.oxigraph_store",
                "prez.sparql.query_fingerprint": query_id,
                "prez.repository.type": "remote",
                "http.response.header.content-type": response_format,
                "prez.oxigraph.rdf_format": str(oxigraph_format),
                "response_size_bytes": len(content_bytes),
                "remote_read_duration_ms": round(read_ms, 1),
                "bulk_load_duration_ms": round(bulk_load_ms, 1),
                "duration_ms": round(total_ms, 1),
            },
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
        read_end = time.perf_counter()
        record_downstream_timing(read_start, read_end)
        read_ms = (read_end - read_start) * 1000
        log.debug(
            "Remote SPARQL tabular query completed",
            extra={
                "event.name": "remote_sparql.tabular_query",
                "prez.sparql.query_fingerprint": query_id,
                "prez.repository.type": "remote",
                "http.response.status_code": response.status_code,
                "remote_read_duration_ms": round(read_ms, 1),
            },
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
            if k.lower() not in {b"host", b"x-request-id"}
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

        request.headers["host"] = httpx.URL(url).host

        send_start = time.perf_counter()
        try:
            response = await self.async_client.send(request, stream=True)
            response_stream = getattr(response, "stream", None)
            if isinstance(response_stream, httpx.AsyncByteStream):
                response.stream = _TimedSparqlStream(response_stream)
        finally:
            send_end = time.perf_counter()
            record_downstream_timing(send_start, send_end)
        send_ms = (send_end - send_start) * 1000
        await self._raise_for_status_with_body(response, query_id)
        total_ms = (time.perf_counter() - total_start) * 1000
        log.debug(
            "Proxied SPARQL request completed",
            extra={
                "event.name": "remote_sparql.proxy",
                "prez.sparql.query_fingerprint": query_id,
                "prez.repository.type": "remote",
                "http.request.method": method,
                "http.response.status_code": response.status_code,
                "response_send_duration_ms": round(send_ms, 1),
                "duration_ms": round(total_ms, 1),
                "prez.sparql.endpoint": _safe_endpoint(settings.sparql_endpoint),
            },
        )
        return response
