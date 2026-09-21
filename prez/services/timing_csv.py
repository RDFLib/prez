import csv
import io
import logging
from datetime import datetime, timezone
from pathlib import Path

from prez.config import settings

TIMING_FIELDS = [
    "ts_utc",
    "event",
    "query_id",
    "method",
    "mediatype",
    "profile",
    "branch",
    "status",
    "endpoint",
    "format",
    "oxigraph_format",
    "bytes",
    "queries",
    "count",
    "store_quads",
    "annotation_quads",
    "elapsed_ms",
    "read_ms",
    "parse_ms",
    "bulk_load_ms",
    "annotations_ms",
    "merge_ms",
    "dump_ms",
    "render_ms",
    "total_ms",
    "details",
]

timing_log = logging.getLogger("prez.timing")


def ensure_timing_csv_header(path_str: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TIMING_FIELDS)
        writer.writeheader()


def log_timing_csv(event: str, **fields) -> None:
    if not settings.timing_csv_enabled:
        return

    row = {name: "" for name in TIMING_FIELDS}
    row["ts_utc"] = datetime.now(timezone.utc).isoformat()
    row["event"] = event

    extras = {}
    for key, value in fields.items():
        if key in row:
            row[key] = value
        else:
            extras[key] = value

    if extras:
        row["details"] = str(extras)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=TIMING_FIELDS)
    writer.writerow(row)
    timing_log.info(buffer.getvalue().rstrip("\r\n"))
