import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from prez.services.timing_csv import log_timing_csv

log = logging.getLogger(__name__)


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


class RequestTimingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code: int | None = None
        response_started_ms: float | None = None
        response_start_sent_ms: float | None = None
        response_complete_ms: float | None = None
        response_complete_sent_ms: float | None = None
        app_returned_ms: float | None = None
        body_bytes = 0
        body_chunks = 0
        header_bytes = 0
        response_start_send_ms = 0.0
        first_body_chunk_ms: float | None = None
        first_body_send_ms: float | None = None
        final_body_chunk_ms: float | None = None
        final_body_send_ms: float | None = None
        max_body_send_ms = 0.0

        async def timed_send(message: Message):
            nonlocal status_code
            nonlocal response_started_ms
            nonlocal response_start_sent_ms
            nonlocal response_complete_ms
            nonlocal response_complete_sent_ms
            nonlocal body_bytes
            nonlocal body_chunks
            nonlocal header_bytes
            nonlocal response_start_send_ms
            nonlocal first_body_chunk_ms
            nonlocal first_body_send_ms
            nonlocal final_body_chunk_ms
            nonlocal final_body_send_ms
            nonlocal max_body_send_ms
            message_type = message["type"]

            if message_type == "http.response.start":
                status_code = message["status"]
                response_started_ms = (time.perf_counter() - start) * 1000
                headers = message.get("headers", [])
                header_bytes = sum(len(name) + len(value) + 4 for name, value in headers)
                send_start = time.perf_counter()
                await send(message)
                response_start_send_ms = (time.perf_counter() - send_start) * 1000
                response_start_sent_ms = (time.perf_counter() - start) * 1000
                return

            if message_type == "http.response.body":
                chunk_ms = (time.perf_counter() - start) * 1000
                chunk_len = len(message.get("body", b""))
                send_start = time.perf_counter()
                body_chunks += 1
                body_bytes += chunk_len
                if first_body_chunk_ms is None:
                    first_body_chunk_ms = chunk_ms
                if not message.get("more_body", False):
                    final_body_chunk_ms = chunk_ms

                await send(message)

                send_ms = (time.perf_counter() - send_start) * 1000
                max_body_send_ms = max(max_body_send_ms, send_ms)
                if first_body_send_ms is None:
                    first_body_send_ms = send_ms
                if not message.get("more_body", False):
                    final_body_send_ms = send_ms
                    response_complete_ms = chunk_ms
                    response_complete_sent_ms = (time.perf_counter() - start) * 1000
                return

            await send(message)

        try:
            await self.app(scope, receive, timed_send)
            app_returned_ms = (time.perf_counter() - start) * 1000
        finally:
            total_ms = (time.perf_counter() - start) * 1000
            route = scope.get("route")
            route_name = getattr(route, "name", "") if route else ""
            path = scope.get("path", "")
            query_string = scope.get("query_string", b"")
            query_len = len(query_string) if query_string else 0
            pre_app_return_ms = app_returned_ms or 0.0
            first_byte_ms = response_started_ms or 0.0
            first_wire_ms = response_start_sent_ms or 0.0
            response_emit_ms = (
                (response_complete_sent_ms - app_returned_ms)
                if response_complete_sent_ms is not None and app_returned_ms is not None
                else 0.0
            )
            app_overhead_after_first_byte_ms = (
                (app_returned_ms - response_started_ms)
                if app_returned_ms is not None and response_started_ms is not None
                else 0.0
            )
            wire_after_app_ms = max(total_ms - pre_app_return_ms, 0.0)
            log.debug(
                "request complete method=%s path=%s route=%s status=%s first_byte_ms=%.1f first_wire_ms=%.1f app_return_ms=%.1f response_complete_ms=%.1f response_complete_sent_ms=%.1f total_ms=%.1f bytes=%s header_bytes=%s chunks=%s start_send_ms=%.1f first_chunk_ms=%.1f first_chunk_send_ms=%.1f final_chunk_ms=%.1f final_chunk_send_ms=%.1f max_chunk_send_ms=%.1f app_after_first_byte_ms=%.1f emit_after_app_ms=%.1f wire_after_app_ms=%.1f query_len=%s",
                scope.get("method", ""),
                path,
                route_name,
                status_code,
                first_byte_ms,
                first_wire_ms,
                pre_app_return_ms,
                response_complete_ms or 0.0,
                response_complete_sent_ms or 0.0,
                total_ms,
                body_bytes,
                header_bytes,
                body_chunks,
                response_start_send_ms,
                first_body_chunk_ms or 0.0,
                first_body_send_ms or 0.0,
                final_body_chunk_ms or 0.0,
                final_body_send_ms or 0.0,
                max_body_send_ms,
                app_overhead_after_first_byte_ms,
                response_emit_ms,
                wire_after_app_ms,
                query_len,
            )
            log_timing_csv(
                "request_complete",
                method=scope.get("method", ""),
                endpoint=route_name or path,
                status=status_code or "",
                bytes=body_bytes,
                elapsed_ms=f"{first_byte_ms:.1f}",
                read_ms=f"{first_wire_ms:.1f}",
                parse_ms=f"{pre_app_return_ms:.1f}",
                dump_ms=f"{(response_complete_ms or 0.0):.1f}",
                render_ms=f"{(response_complete_sent_ms or 0.0):.1f}",
                total_ms=f"{total_ms:.1f}",
                details=(
                    f"path={path} query_len={query_len} header_bytes={header_bytes} "
                    f"chunks={body_chunks} start_send_ms={response_start_send_ms:.1f} "
                    f"first_body_chunk_ms={(first_body_chunk_ms or 0.0):.1f} "
                    f"first_body_send_ms={(first_body_send_ms or 0.0):.1f} "
                    f"final_body_chunk_ms={(final_body_chunk_ms or 0.0):.1f} "
                    f"final_body_send_ms={(final_body_send_ms or 0.0):.1f} "
                    f"max_body_send_ms={max_body_send_ms:.1f} "
                    f"app_after_first_byte_ms={app_overhead_after_first_byte_ms:.1f} "
                    f"emit_after_app_ms={response_emit_ms:.1f} "
                    f"wire_after_app_ms={wire_after_app_ms:.1f}"
                ),
            )
