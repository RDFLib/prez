"""Central logging configuration and request correlation support for Prez.

Application modules should obtain loggers with :func:`get_logger`. The adapter adds
request context to records emitted during HTTP requests; startup and shutdown output
remains concise. Durations are always monotonic measurements named ``*_duration_ms`` and sizes/counts
include their unit in the field name.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"
NO_REQUEST_ID = "-"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_request_id: ContextVar[str] = ContextVar("prez_request_id", default=NO_REQUEST_ID)


@dataclass
class DownstreamTimingContext:
    """Downstream wait spans collected during one request.

    The mutable context is intentionally shared by child asyncio tasks.  Storing spans,
    rather than just adding durations, lets the middleware avoid double-counting
    concurrent downstream calls when separating wall time from Prez processing time.
    """

    spans: list[tuple[float, float]] = field(default_factory=list)


_downstream_timings: ContextVar[DownstreamTimingContext | None] = ContextVar(
    "prez_downstream_timings", default=None
)


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


def get_request_id() -> str:
    """Return the request ID in the current async/thread context."""
    return _request_id.get()


def new_request_id(candidate: str | None = None) -> str:
    """Use a safe caller-supplied ID, or create a new opaque ID.

    Restricting accepted values prevents unbounded or control-character log/header
    injection while supporting common UUID and distributed tracing ID formats.
    """
    if candidate:
        candidate = candidate.strip()
        if _REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
    return str(uuid4())


def bind_request_id(request_id: str) -> Token[str]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


class _ContextLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: Any, kwargs: dict[str, Any]):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("request_id", get_request_id())
        return msg, kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """Return a Prez logger carrying the current correlation context."""
    return _ContextLoggerAdapter(logging.getLogger(name), {})


class _PrezFormatter(logging.Formatter):
    """Uvicorn-style output, with request metadata only during a request."""

    converter = staticmethod(__import__("time").gmtime)
    _COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    _RESET = "\033[0m"

    def __init__(self, use_colors: bool):
        super().__init__()
        self.use_colors = use_colors
        self.timestamp_formatter = _UtcFormatter(
            "%(asctime)s.%(msecs)03dZ", datefmt="%Y-%m-%dT%H:%M:%S"
        )

    @staticmethod
    def _coerce_value(field_name: str, value: str) -> Any:
        """Coerce fields whose names explicitly identify a numeric or bool value."""
        if field_name.startswith(("has_", "is_")):
            if value in {"true", "True"}:
                return True
            if value in {"false", "False"}:
                return False
        numeric_names = {"duration_ms", "size_bytes", "count", "status", "percent"}
        numeric_suffixes = (
            "_duration_ms",
            "_size_bytes",
            "_count",
            "_status",
            "_percent",
        )
        if field_name not in numeric_names and not field_name.endswith(
            numeric_suffixes
        ):
            return value
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    def _payload(self, record: logging.LogRecord, message: str) -> dict[str, Any]:
        supplied_fields = getattr(record, "structured_fields", None)
        if supplied_fields is not None:
            payload = dict(supplied_fields)
        elif message.startswith("event="):
            payload = {}
            spans: list[tuple[int, int]] = []
            for match in re.finditer(r"(?:^|\s)([A-Za-z][\w]*)=([^\s,)]+)", message):
                field_name = match.group(1)
                payload[field_name] = self._coerce_value(field_name, match.group(2))
                spans.append(match.span())
            remainder = message
            for start, end in reversed(spans):
                remainder = remainder[:start] + remainder[end:]
            remainder = re.sub(r"\s+", " ", remainder).strip(" ()")
            if remainder:
                payload["message"] = remainder
        else:
            payload = {"message": message}

        if record.exc_info:
            payload.setdefault("exception", self.formatException(record.exc_info))
        if record.levelno == logging.DEBUG:
            payload.setdefault("logger", record.name)
        request_id = getattr(record, "request_id", NO_REQUEST_ID)
        if request_id != NO_REQUEST_ID:
            payload.setdefault("request_id", request_id)
        return payload

    def format(self, record: logging.LogRecord) -> str:
        level_prefix = f"{record.levelname}:".ljust(9) + " "
        if self.use_colors:
            color = self._COLORS.get(record.levelno, "")
            if color:
                level_prefix = f"{color}{level_prefix}{self._RESET}"

        prefix = self.timestamp_formatter.format(record) + " " + level_prefix
        message = record.getMessage()
        return prefix + json.dumps(
            self._payload(record, message), separators=(",", ":"), default=str
        )


class _UtcFormatter(logging.Formatter):
    converter = staticmethod(__import__("time").gmtime)


def _log_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("../logs") / f"prez-{timestamp}.log"


def setup_logger(settings) -> None:
    """Configure structured Prez application logging."""
    logger = logging.getLogger("prez")
    logger.setLevel(settings.log_level.upper())
    # Preserve propagation for host applications and test/observability handlers.
    logger.propagate = True
    handlers: list[logging.Handler] = []
    if settings.log_output in {"file", "both"}:
        logfile = _log_path()
        logfile.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logfile, encoding="utf-8")
        file_handler.setFormatter(_PrezFormatter(use_colors=False))
        handlers.append(file_handler)
    if settings.log_output in {"stdout", "both"}:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(_PrezFormatter(use_colors=True))
        handlers.append(stdout_handler)
    for handler in handlers:
        handler.setLevel(settings.log_level.upper())
    logger.handlers = handlers
