"""Central logging configuration and request correlation support for Prez.

Application modules should obtain loggers with :func:`get_logger`.  The adapter adds
``request_id`` to every record, including records emitted outside an HTTP request.
Durations are always monotonic measurements named ``*_duration_ms`` and sizes/counts
include their unit in the field name.
"""

from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"
NO_REQUEST_ID = "-"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_request_id: ContextVar[str] = ContextVar("prez_request_id", default=NO_REQUEST_ID)


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


class _UtcFormatter(logging.Formatter):
    converter = staticmethod(__import__("time").gmtime)


def _log_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("../logs") / f"prez-{timestamp}.log"


def setup_logger(settings) -> None:
    """Configure all Prez logs and the optional normalized timing CSV sink."""
    logger = logging.getLogger("prez")
    logger.setLevel(settings.log_level.upper())
    # Preserve propagation for host applications and test/observability handlers.
    logger.propagate = True
    formatter = _UtcFormatter(
        fmt=(
            "timestamp_utc=%(asctime)s.%(msecs)03dZ level=%(levelname)s "
            "logger=%(name)s request_id=%(request_id)s message=%(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handlers: list[logging.Handler] = []
    if settings.log_output in {"file", "both"}:
        logfile = _log_path()
        logfile.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(logfile, encoding="utf-8"))
    if settings.log_output in {"stdout", "both"}:
        handlers.append(logging.StreamHandler(sys.stdout))
    for handler in handlers:
        handler.setLevel(settings.log_level.upper())
        handler.setFormatter(formatter)
    logger.handlers = handlers

    # Imported lazily to avoid making the logging and metrics modules cyclic.
    from prez.services.timing_csv import configure_timing_csv

    configure_timing_csv(settings.timing_csv_enabled, settings.timing_csv_path)
