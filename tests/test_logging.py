import csv
import io
import logging
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from prez.config import Settings
from prez.middleware import RequestContextMiddleware, RequestTimingMiddleware
from prez.repositories.remote_sparql import RemoteSparqlRepo
from prez.services.prez_logging import (
    REQUEST_ID_HEADER,
    bind_request_id,
    get_logger,
    get_request_id,
    new_request_id,
    reset_request_id,
    setup_logger,
)
from prez.services.timing_csv import (
    TIMING_FIELDS,
    configure_timing_csv,
    log_timing_csv,
)


def test_logger_adds_bound_request_id_to_every_record():
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    raw_logger = logging.getLogger("prez.test.context")
    handler = Capture()
    raw_logger.addHandler(handler)
    raw_logger.setLevel(logging.INFO)
    token = bind_request_id("client-trace-42")
    try:
        get_logger("prez.test.context").info("event=test")
    finally:
        reset_request_id(token)
        raw_logger.removeHandler(handler)

    assert records[0].request_id == "client-trace-42"
    assert get_request_id() == "-"


def test_setup_logger_emits_utc_schema_and_default_context(monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr("prez.services.prez_logging.sys.stdout", output)
    prez_logger = logging.getLogger("prez")
    old_handlers = prez_logger.handlers[:]
    old_level = prez_logger.level
    try:
        setup_logger(Settings(_env_file=None, log_output="stdout"))
        get_logger("prez.test.configuration").info("event=configuration.test")
    finally:
        for handler in prez_logger.handlers:
            handler.close()
        prez_logger.handlers = old_handlers
        prez_logger.setLevel(old_level)

    line = output.getvalue()
    assert "timestamp_utc=" in line
    assert "Z level=INFO" in line
    assert "request_id=-" in line
    assert "message=event=configuration.test" in line


def _correlation_app(records):
    app = FastAPI()
    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    async def endpoint():
        records.append(get_request_id())
        get_logger("prez.test.request").info("event=test.request")
        return {"ok": True}

    return app


def test_request_id_is_preserved_through_request_and_returned():
    seen = []
    with TestClient(_correlation_app(seen)) as client:
        response = client.get("/test", headers={REQUEST_ID_HEADER: "upstream-123"})

    assert response.headers[REQUEST_ID_HEADER] == "upstream-123"
    assert seen == ["upstream-123"]


def test_invalid_or_missing_request_id_is_replaced():
    seen = []
    with TestClient(_correlation_app(seen)) as client:
        response = client.get("/test", headers={REQUEST_ID_HEADER: "bad\tid"})

    generated = response.headers[REQUEST_ID_HEADER]
    assert generated == seen[0]
    assert generated != "bad\tid"
    assert new_request_id(generated) == generated


def test_timing_csv_uses_normalized_schema_and_request_id(tmp_path: Path):
    path = tmp_path / "timing.csv"
    configure_timing_csv(True, str(path))
    token = bind_request_id("metrics-request")
    try:
        log_timing_csv(
            "request.complete",
            http_method="GET",
            response_size_bytes=12,
            total_duration_ms="3.2",
        )
    finally:
        reset_request_id(token)
        configure_timing_csv(False, str(path))

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["request_id"] == "metrics-request"
    assert rows[0]["response_size_bytes"] == "12"
    assert rows[0]["total_duration_ms"] == "3.2"
    assert "elapsed_ms" not in TIMING_FIELDS
    assert "bytes" not in TIMING_FIELDS
    assert all(
        not name.endswith("_ms") or name.endswith("_duration_ms")
        for name in TIMING_FIELDS
    )


@pytest.mark.asyncio
async def test_remote_sparql_propagates_request_id(monkeypatch):
    received = {}

    def respond(request: httpx.Request):
        received.update(request.headers)
        return httpx.Response(200, headers={"content-type": "text/turtle"}, content=b"")

    monkeypatch.setattr(
        "prez.repositories.remote_sparql.settings.sparql_endpoint",
        "http://example.test/sparql",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        repo = RemoteSparqlRepo(client)
        token = bind_request_id("downstream-456")
        try:
            response = await repo._send_query("CONSTRUCT WHERE {}")
            await response.aclose()
        finally:
            reset_request_id(token)

    assert received[REQUEST_ID_HEADER.lower()] == "downstream-456"
