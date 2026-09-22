import asyncio
import io
import json
import logging
import re
import sys
import time

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from prez.config import Settings
from prez.middleware import (
    RequestContextMiddleware,
    RequestTimingMiddleware,
    _union_duration_ms,
)
from prez.repositories.remote_sparql import RemoteSparqlRepo
from prez.services.prez_logging import (
    REQUEST_ID_HEADER,
    _PrezFormatter,
    bind_downstream_timings,
    bind_request_id,
    get_downstream_timing_spans,
    get_logger,
    get_request_id,
    new_request_id,
    record_downstream_timing,
    reset_downstream_timings,
    reset_request_id,
    setup_logger,
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


def test_setup_logger_keeps_startup_output_concise_and_colored(monkeypatch):
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
    assert "\033[32m" in line
    plain_line = re.sub(r"\033\[[0-9;]*m", "", line).rstrip()
    match = re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z INFO:     (.+)",
        plain_line,
    )
    assert match is not None
    assert json.loads(match.group(1)) == {"event": "configuration.test"}
    assert "request_id" not in plain_line
    assert "logger=" not in plain_line
    assert "timestamp_utc=" not in plain_line


def test_debug_logs_have_a_json_payload(monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr("prez.services.prez_logging.sys.stdout", output)
    prez_logger = logging.getLogger("prez")
    old_handlers = prez_logger.handlers[:]
    old_level = prez_logger.level
    try:
        setup_logger(Settings(_env_file=None, log_output="stdout", log_level="DEBUG"))
        token = bind_request_id("debug-request")
        try:
            get_logger("prez.test.debug").debug(
                "event=debug.metric duration_ms=1.2 identifier=1234"
            )
        finally:
            reset_request_id(token)
    finally:
        for handler in prez_logger.handlers:
            handler.close()
        prez_logger.handlers = old_handlers
        prez_logger.setLevel(old_level)

    plain_line = re.sub(r"\033\[[0-9;]*m", "", output.getvalue()).rstrip()
    payload = json.loads(plain_line.split("DEBUG:    ", maxsplit=1)[1])
    assert payload == {
        "event": "debug.metric",
        "duration_ms": 1.2,
        "identifier": "1234",
        "logger": "prez.test.debug",
        "request_id": "debug-request",
    }


def test_formatter_only_parses_explicit_events_and_preserves_tracebacks():
    formatter = _PrezFormatter(use_colors=False)
    ordinary_record = logging.LogRecord(
        "prez.test", logging.INFO, __file__, 1, "URL ?limit=10 enabled=true", (), None
    )
    ordinary_line = formatter.format(ordinary_record)
    ordinary_payload = json.loads(ordinary_line[ordinary_line.index("{") :])
    assert ordinary_payload == {"message": "URL ?limit=10 enabled=true"}

    try:
        raise RuntimeError("formatter failure")
    except RuntimeError:
        exception_record = logging.LogRecord(
            "prez.test",
            logging.ERROR,
            __file__,
            1,
            "Request failed",
            (),
            sys.exc_info(),
        )
    exception_line = formatter.format(exception_record)
    exception_payload = json.loads(exception_line[exception_line.index("{") :])
    assert exception_payload["message"] == "Request failed"
    assert "RuntimeError: formatter failure" in exception_payload["exception"]


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


def test_request_completion_logs_downstream_and_prez_breakdown():
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    app = FastAPI()
    app.add_middleware(RequestTimingMiddleware)

    @app.get("/timed")
    async def timed_endpoint():
        started_at = time.perf_counter()
        await asyncio.sleep(0.002)
        record_downstream_timing(started_at, time.perf_counter())
        return {"ok": True}

    logger = logging.getLogger("prez.middleware")
    handler = Capture()
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        with TestClient(app) as client:
            assert client.get("/timed").status_code == 200
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    completion = next(
        record
        for record in records
        if getattr(record, "structured_fields", {}).get("event") == "request.complete"
    )
    assert completion.levelno == logging.INFO
    details = completion.structured_fields
    assert details["http_method"] == "GET"
    assert details["path"] == "/timed"
    assert details["http_status"] == 200
    assert "downstream_duration_ms" in details
    assert "downstream_sparql_duration_ms" not in details
    assert "prez_duration_ms" in details


def test_downstream_timing_merges_concurrent_waits():
    assert _union_duration_ms([(1.0, 1.010), (1.005, 1.020)]) == pytest.approx(20.0)

    token = bind_downstream_timings()
    try:
        record_downstream_timing(1.0, 1.01)
        assert get_downstream_timing_spans() == [(1.0, 1.01)]
    finally:
        reset_downstream_timings(token)


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


@pytest.mark.asyncio
async def test_sparql_proxy_tracks_downstream_wait_without_forwarding_placeholder_id(
    monkeypatch,
):
    received = {}

    def respond(request: httpx.Request):
        received.update(request.headers)
        return httpx.Response(200, content=b"result")

    monkeypatch.setattr(
        "prez.repositories.remote_sparql.settings.sparql_endpoint",
        "http://example.test/sparql",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        repo = RemoteSparqlRepo(client)
        token = bind_downstream_timings()
        try:
            response = await repo.sparql("SELECT * WHERE {}", [])
            await response.aread()
            assert get_downstream_timing_spans()
        finally:
            reset_downstream_timings(token)

    assert REQUEST_ID_HEADER.lower() not in received
