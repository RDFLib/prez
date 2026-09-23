import re
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from prez.services.prez_logging import (
    bind_downstream_timings,
    bind_request_ids,
    get_downstream_timing_spans,
    get_logger,
    get_request_log_attributes,
    new_request_id,
    reset_downstream_timings,
    reset_request_ids,
)

log = get_logger(__name__)

REQUEST_ID_HEADER = b"x-request-id"
CLIENT_REQUEST_ID_RESPONSE_HEADER = b"x-client-request-id"
_CLIENT_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")


def _client_request_id(scope: Scope) -> str | None:
    """Return one safe client-supplied request ID, ignoring invalid input."""
    values = [
        value
        for name, value in scope.get("headers", [])
        if name.lower() == REQUEST_ID_HEADER
    ]
    if len(values) != 1:
        return None
    try:
        value = values[0].decode("ascii")
    except UnicodeDecodeError:
        return None
    return value if _CLIENT_REQUEST_ID_PATTERN.fullmatch(value) else None


class RequestCorrelationMiddleware:
    """Correlate logs by Prez and optional client IDs.

    These IDs are application correlation values, not W3C trace IDs. They must remain
    separate from the ``trace_id`` and ``span_id`` fields supplied by future OTEL
    instrumentation.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = new_request_id()
        client_request_id = _client_request_id(scope)
        tokens = bind_request_ids(request_id, client_request_id)

        async def correlated_send(message: Message):
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.setdefault("headers", [])
                    if name.lower()
                    not in {REQUEST_ID_HEADER, CLIENT_REQUEST_ID_RESPONSE_HEADER}
                ]
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                if client_request_id is not None:
                    headers.append(
                        (
                            CLIENT_REQUEST_ID_RESPONSE_HEADER,
                            client_request_id.encode("ascii"),
                        )
                    )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, correlated_send)
        finally:
            reset_request_ids(tokens)


def _estimate_header_line_size(name: str, value: str) -> int:
    return len(name.encode("latin-1")) + len(value.encode("latin-1")) + 4


def _estimate_response_header_bytes(response) -> int:
    return sum(len(name) + len(value) + 4 for name, value in response.raw_headers)


def _trim_link_header_to_budget(link_value: str, budget: int) -> str | None:
    if budget <= 0:
        return None

    entries = [entry.strip() for entry in link_value.split(",") if entry.strip()]
    if not entries:
        return None

    kept_entries: list[str] = []
    for entry in entries:
        candidate = ", ".join([*kept_entries, entry])
        if _estimate_header_line_size("link", candidate) <= budget:
            kept_entries.append(entry)
        else:
            break

    if not kept_entries:
        return None
    return ", ".join(kept_entries)


def _drop_optional_headers_to_fit(response, max_header_bytes: int) -> None:
    protected_headers = {
        "content-type",
        "content-length",
        "content-encoding",
        "transfer-encoding",
        "location",
    }

    header_sizes: dict[str, int] = {}
    original_names: dict[str, str] = {}
    for raw_name, raw_value in response.raw_headers:
        header_name = raw_name.decode("latin-1").lower()
        original_names.setdefault(header_name, raw_name.decode("latin-1"))
        header_sizes[header_name] = header_sizes.get(header_name, 0) + (
            len(raw_name) + len(raw_value) + 4
        )

    removable_headers = sorted(
        (
            (name, size)
            for name, size in header_sizes.items()
            if name not in protected_headers and name != "link"
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    for header_name, _ in removable_headers:
        del response.headers[original_names[header_name]]
        if _estimate_response_header_bytes(response) <= max_header_bytes:
            return


def create_response_header_budget_middleware(max_header_bytes: int | None):
    async def enforce_response_header_budget(request: Request, call_next):
        response = await call_next(request)

        if not max_header_bytes or max_header_bytes <= 0:
            return response

        total_header_bytes = _estimate_response_header_bytes(response)
        if total_header_bytes <= max_header_bytes:
            return response

        link_value = response.headers.get("link")
        if link_value is not None:
            other_headers_size = total_header_bytes - _estimate_header_line_size(
                "link", link_value
            )
            trimmed_link_value = _trim_link_header_to_budget(
                link_value, max_header_bytes - other_headers_size
            )
            if trimmed_link_value is None:
                del response.headers["link"]
                log.warning(
                    "Dropped Link response header to stay within %s byte header budget for %s",
                    max_header_bytes,
                    request.url.path,
                )
            elif trimmed_link_value != link_value:
                response.headers["link"] = trimmed_link_value
                log.warning(
                    "Trimmed Link response header to stay within %s byte header budget for %s",
                    max_header_bytes,
                    request.url.path,
                )

        if _estimate_response_header_bytes(response) > max_header_bytes:
            _drop_optional_headers_to_fit(response, max_header_bytes)

        final_header_bytes = _estimate_response_header_bytes(response)
        if final_header_bytes > max_header_bytes:
            log.warning(
                "Response headers still exceed budget after trimming: %s bytes for %s",
                final_header_bytes,
                request.url.path,
            )

        return response

    return enforce_response_header_budget


def create_validate_header_middleware(required_header: dict[str, str] | None):
    async def validate_header(request: Request, call_next):
        if required_header:
            header_name, expected_value = next(iter(required_header.items()))
            if (
                header_name not in request.headers
                or request.headers[header_name] != expected_value
            ):
                return JSONResponse(  # attempted to use Exception and although it was caught it did not propagate
                    status_code=400,
                    content={
                        "error": "Header Validation Error",
                        "message": f"Missing or invalid header: {header_name}",
                        "code": "HEADER_VALIDATION_ERROR",
                    },
                )
        return await call_next(request)

    return validate_header


def _union_duration_ms(spans: list[tuple[float, float]]) -> float:
    """Return wall time covered by spans, counting overlaps only once."""
    if not spans:
        return 0.0
    ordered = sorted(spans)
    total = 0.0
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    return (total + current_end - current_start) * 1000


class RequestTimingMiddleware:
    """Emit one normalized completion event for each HTTP request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        downstream_token = bind_downstream_timings()
        status_code: int | None = None
        response_started_at: float | None = None
        response_completed_at: float | None = None
        response_size_bytes = 0
        response_body_chunk_count = 0
        response_header_size_bytes = 0

        async def timed_send(message: Message):
            nonlocal status_code, response_started_at, response_completed_at
            nonlocal response_size_bytes, response_body_chunk_count
            nonlocal response_header_size_bytes
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started_at = time.perf_counter()
                response_header_size_bytes = sum(
                    len(name) + len(value) + 4
                    for name, value in message.get("headers", [])
                )
            elif message["type"] == "http.response.body":
                response_body_chunk_count += 1
                response_size_bytes += len(message.get("body", b""))
                if not message.get("more_body", False):
                    response_completed_at = time.perf_counter()
            await send(message)

        try:
            await self.app(scope, receive, timed_send)
        finally:
            completed_at = time.perf_counter()
            path = scope.get("path", "")
            start_duration_ms = (
                (response_started_at - start) * 1000 if response_started_at else 0.0
            )
            send_duration_ms = (
                (response_completed_at - response_started_at) * 1000
                if response_completed_at and response_started_at
                else 0.0
            )
            total_duration_ms = (completed_at - start) * 1000
            downstream_spans = get_downstream_timing_spans()
            downstream_duration_ms = _union_duration_ms(downstream_spans)
            prez_duration_ms = max(0.0, total_duration_ms - downstream_duration_ms)
            request_details = {
                **get_request_log_attributes(),
                "event.name": "request.complete",
                "http.request.method": scope.get("method", ""),
                "http.response.status_code": status_code,
                "url.path": path,
                "duration_ms": round(total_duration_ms, 1),
                "downstream_duration_ms": round(downstream_duration_ms, 1),
                "prez_duration_ms": round(prez_duration_ms, 1),
                "time_to_response_start_duration_ms": round(start_duration_ms, 1),
                "response_send_duration_ms": round(send_duration_ms, 1),
                "response_size_bytes": response_size_bytes,
                "response_header_size_bytes": response_header_size_bytes,
                "response_body_chunk_count": response_body_chunk_count,
                "query_string_size_bytes": len(scope.get("query_string", b"")),
            }
            try:
                log.info("Request completed", extra=request_details)
            finally:
                reset_downstream_timings(downstream_token)
