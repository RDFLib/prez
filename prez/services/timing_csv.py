"""Optional CSV event metrics using the Prez logging field schema.

Every duration is a monotonic measurement in milliseconds and ends in
``_duration_ms``.  Sizes end in ``_size_bytes`` and cardinalities in ``_count``.
The same request ID used by application logs is present in every row.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from prez.services.prez_logging import get_request_id

TIMING_FIELDS = [
    "timestamp_utc",
    "event",
    "request_id",
    "query_id",
    "http_method",
    "media_type",
    "profile",
    "branch",
    "http_status",
    "endpoint",
    "format",
    "oxigraph_format",
    "response_size_bytes",
    "response_header_size_bytes",
    "query_string_size_bytes",
    "query_count",
    "item_count",
    "store_quad_count",
    "annotation_quad_count",
    "response_body_chunk_count",
    "cache_hit_count",
    "cache_miss_count",
    "cache_lookup_duration_ms",
    "cache_write_duration_ms",
    "remote_read_duration_ms",
    "parse_duration_ms",
    "bulk_load_duration_ms",
    "system_repository_duration_ms",
    "annotation_repository_duration_ms",
    "data_repository_duration_ms",
    "annotation_duration_ms",
    "merge_duration_ms",
    "serialization_duration_ms",
    "render_duration_ms",
    "link_generation_duration_ms",
    "time_to_response_start_duration_ms",
    "response_send_duration_ms",
    "downstream_duration_ms",
    "prez_duration_ms",
    "total_duration_ms",
    "details",
]

_timing_log = logging.getLogger("prez.timing")
_enabled = False


def ensure_timing_csv_header(path_str: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        with path.open(newline="", encoding="utf-8") as file:
            existing_fields = next(csv.reader(file), [])
        if existing_fields == TIMING_FIELDS:
            return
        # Never append normalized rows beneath an incompatible legacy header.
        legacy_path = path.with_suffix(f"{path.suffix}.legacy")
        counter = 1
        while legacy_path.exists():
            legacy_path = path.with_suffix(f"{path.suffix}.legacy.{counter}")
            counter += 1
        path.replace(legacy_path)
    with path.open("a", newline="", encoding="utf-8") as file:
        csv.DictWriter(file, fieldnames=TIMING_FIELDS).writeheader()


def configure_timing_csv(enabled: bool, path_str: str) -> None:
    """Configure the dedicated CSV sink; safe to call for each app lifespan."""
    global _enabled
    _enabled = enabled
    _timing_log.setLevel(logging.INFO)
    _timing_log.propagate = False
    for handler in _timing_log.handlers:
        handler.close()
    _timing_log.handlers = []
    if enabled:
        ensure_timing_csv_header(path_str)
        handler = logging.FileHandler(path_str, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        _timing_log.handlers = [handler]


def log_timing_csv(event: str, **fields) -> None:
    """Write one normalized metric event.

    Unknown event-specific values are retained as JSON in ``details`` instead of
    silently changing the stable CSV columns.
    """
    if not _enabled:
        return
    row = {name: "" for name in TIMING_FIELDS}
    row.update(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        event=event,
        request_id=get_request_id(),
    )
    extras = {}
    for key, value in fields.items():
        if key in row:
            row[key] = value
        else:
            extras[key] = value
    if extras:
        existing = fields.get("details")
        if existing:
            extras["description"] = existing
        row["details"] = json.dumps(extras, sort_keys=True, default=str)
    buffer = io.StringIO()
    csv.DictWriter(buffer, fieldnames=TIMING_FIELDS).writerow(row)
    _timing_log.info(buffer.getvalue().rstrip("\r\n"))
