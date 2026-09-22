"""Central logging configuration for Prez.

Application code uses ordinary :mod:`logging` loggers and supplies structured data as
flat, typed ``extra`` attributes. Request correlation IDs are added at the stdout handler
boundary. They are deliberately distinct from OpenTelemetry trace and span IDs. The
handler remains a temporary seam that can be replaced by an OpenTelemetry logging
handler in the future.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar


@dataclass
class DownstreamTimingContext:
    """Downstream wait spans collected during one request.

    This is temporary telemetry state, not logging context.  The mutable context is
    intentionally shared by child asyncio tasks.  Storing spans lets the middleware
    avoid double-counting concurrent downstream calls.
    """

    spans: list[tuple[float, float]] = field(default_factory=list)


_downstream_timings: ContextVar[DownstreamTimingContext | None] = ContextVar(
    "prez_downstream_timings", default=None
)
_request_id: ContextVar[str | None] = ContextVar("prez_request_id", default=None)
_client_request_id: ContextVar[str | None] = ContextVar(
    "prez_client_request_id", default=None
)


def new_request_id() -> str:
    """Return an opaque Prez request correlation ID.

    This is not a W3C trace ID and must not be used as one.
    """
    return uuid.uuid4().hex


def bind_request_ids(
    request_id: str, client_request_id: str | None
) -> tuple[Token[str | None], Token[str | None]]:
    return _request_id.set(request_id), _client_request_id.set(client_request_id)


def get_request_log_attributes() -> dict[str, str]:
    attributes: dict[str, str] = {}
    request_id = _request_id.get()
    client_request_id = _client_request_id.get()
    if request_id is not None:
        attributes["prez.request.id"] = request_id
    if client_request_id is not None:
        attributes["prez.client_request.id"] = client_request_id
    return attributes


def reset_request_ids(
    tokens: tuple[Token[str | None], Token[str | None]],
) -> None:
    request_token, client_request_token = tokens
    _client_request_id.reset(client_request_token)
    _request_id.reset(request_token)


def bind_downstream_timings() -> Token[DownstreamTimingContext | None]:
    return _downstream_timings.set(DownstreamTimingContext())


def record_downstream_timing(started_at: float, ended_at: float) -> None:
    """Record a monotonic interval spent awaiting the downstream SPARQL service."""
    context = _downstream_timings.get()
    if context is not None and ended_at >= started_at:
        context.spans.append((started_at, ended_at))


def get_downstream_timing_spans() -> list[tuple[float, float]]:
    context = _downstream_timings.get()
    return list(context.spans) if context is not None else []


def reset_downstream_timings(token: Token[DownstreamTimingContext | None]) -> None:
    _downstream_timings.reset(token)


def get_logger(name: str) -> logging.Logger:
    """Return a standard Python logger without adding or transforming context."""
    return logging.getLogger(name)


_STANDARD_RECORD_ATTRIBUTES = frozenset(logging.makeLogRecord({}).__dict__) | {
    "asctime",
    "message",
}


def _custom_attributes(record: logging.LogRecord) -> dict[str, Any]:
    """Return only fields supplied through ``extra`` on this record."""
    return {
        name: value
        for name, value in record.__dict__.items()
        if name not in _STANDARD_RECORD_ATTRIBUTES
    }


def _json_default(value: Any) -> str:
    """Keep logging robust when a caller supplies a non-JSON application value."""
    return str(value)


def _json_value(value: Any) -> Any:
    """Replace non-finite floats, which JSON does not define, without changing types otherwise."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


class _RequestCorrelationFilter(logging.Filter):
    """Attach active request IDs without changing application logger calls."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name, value in get_request_log_attributes().items():
            if name not in record.__dict__:
                record.__dict__[name] = value
        return True


class _ConsoleFormatter(logging.Formatter):
    """Concise human-readable formatter for local and interactive use."""

    _COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    _RESET = "\033[0m"

    def __init__(self, use_colors: bool = False):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = _utc_timestamp(record.created)
        level = record.levelname
        if self.use_colors:
            color = self._COLORS.get(record.levelno, "")
            if color:
                level = f"{color}{level}{self._RESET}"

        output = f"{timestamp} {level} {record.name}: {record.getMessage()}"
        attributes = _custom_attributes(record)
        if attributes:
            fields = " ".join(
                f"{name}={json.dumps(_json_value(value), default=_json_default, ensure_ascii=False)}"
                for name, value in attributes.items()
            )
            output = f"{output} {fields}"
        if record.exc_info:
            output = f"{output}\n{self.formatException(record.exc_info)}"
        return output


class _JsonFormatter(logging.Formatter):
    """Format each record as one newline-safe JSON object."""

    def __init__(self, service_version: str):
        super().__init__()
        self.resource = {
            "service.name": "prez",
            "service.version": service_version,
        }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_timestamp(record.created),
            "severity_text": record.levelname,
            "body": record.getMessage(),
            "logger.name": record.name,
            "attributes": {
                name: _json_value(value)
                for name, value in _custom_attributes(record).items()
            },
            "resource": self.resource,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(
            payload,
            default=_json_default,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )


def _utc_timestamp(created: float) -> str:
    return (
        datetime.fromtimestamp(created, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def setup_logger(settings: Any) -> None:
    """Configure the ``prez`` logger with one stdout handler.

    Calling this function repeatedly replaces the configured handler rather than adding
    another one.  Prez does not create log files; process supervisors and collectors are
    expected to consume stdout.
    """
    logger = logging.getLogger("prez")
    level = settings.log_level.upper()
    logger.setLevel(level)
    logger.disabled = False
    # This boundary owns Prez output.  Disabling propagation avoids a second copy when a
    # host application also configures the root logger.
    logger.propagate = False

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(_RequestCorrelationFilter())
    if settings.log_format == "json":
        service_version = str(settings.prez_version or "unknown")
        handler.setFormatter(_JsonFormatter(service_version))
    else:
        handler.setFormatter(_ConsoleFormatter(use_colors=sys.stdout.isatty()))
    logger.addHandler(handler)
