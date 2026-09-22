import asyncio
import io
import json
import logging
import sys
import time
from datetime import datetime

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from prez.config import Settings
from prez.middleware import RequestTimingMiddleware, _union_duration_ms
from prez.repositories.remote_sparql import RemoteSparqlRepo
from prez.services.prez_logging import (
    _ConsoleFormatter,
    _JsonFormatter,
    bind_downstream_timings,
    get_downstream_timing_spans,
    get_logger,
    record_downstream_timing,
    reset_downstream_timings,
    setup_logger,
)


@pytest.fixture
def isolated_prez_logger():
    """Restore the package logger without letting setup close existing handlers."""
    logger = logging.getLogger("prez")
    previous_handlers = logger.handlers[:]
    previous_level = logger.level
    previous_disabled = logger.disabled
    previous_propagate = logger.propagate
    logger.handlers = []
    try:
        yield logger
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)
        logger.disabled = previous_disabled
        logger.propagate = previous_propagate


def test_get_logger_returns_standard_logger():
    assert type(get_logger("prez.test.logging")) is logging.Logger


def test_console_formatter_is_human_readable_without_parsing_message_fields():
    record = logging.LogRecord(
        "prez.test.logging",
        logging.INFO,
        __file__,
        1,
        "URL ?limit=10 enabled=true",
        (),
        None,
    )
    record.__dict__.update({"event.name": "test.complete", "result.count": 3})

    output = _ConsoleFormatter(use_colors=False).format(record)

    timestamp, remainder = output.split(" ", maxsplit=1)
    assert datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert "INFO" in remainder
    assert "prez.test.logging" in remainder
    assert "URL ?limit=10 enabled=true" in remainder
    assert 'event.name="test.complete"' in remainder
    assert "result.count=3" in remainder


def test_json_formatter_preserves_types_and_exception_as_one_plain_json_line():
    formatter = _JsonFormatter("1.2.3")
    try:
        raise RuntimeError("formatting failed")
    except RuntimeError:
        record = logging.LogRecord(
            "prez.test.logging",
            logging.ERROR,
            __file__,
            1,
            "Request failed with value=%s",
            (7,),
            sys.exc_info(),
        )
    record.__dict__.update(
        {
            "event.name": "request.failed",
            "duration_ms": 1.25,
            "cached": False,
            "optional": None,
        }
    )

    line = formatter.format(record)
    payload = json.loads(line)

    assert len(line.splitlines()) == 1
    assert "\033[" not in line
    assert line.startswith("{") and line.endswith("}")
    assert payload["timestamp"].endswith("Z")
    assert payload["severity_text"] == "ERROR"
    assert payload["body"] == "Request failed with value=7"
    assert payload["logger.name"] == "prez.test.logging"
    assert payload["attributes"] == {
        "event.name": "request.failed",
        "duration_ms": 1.25,
        "cached": False,
        "optional": None,
    }
    assert isinstance(payload["attributes"]["duration_ms"], float)
    assert payload["attributes"]["cached"] is False
    assert payload["attributes"]["optional"] is None
    assert "RuntimeError: formatting failed" in payload["exception"]
    assert payload["resource"] == {
        "service.name": "prez",
        "service.version": "1.2.3",
    }


def test_json_formatter_does_not_parse_ordinary_key_value_message():
    record = logging.LogRecord(
        "prez.test.logging",
        logging.INFO,
        __file__,
        1,
        "URL ?limit=10 enabled=true count=7 optional=null",
        (),
        None,
    )

    payload = json.loads(_JsonFormatter("1.2.3").format(record))

    assert payload["body"] == "URL ?limit=10 enabled=true count=7 optional=null"
    assert payload["attributes"] == {}


@pytest.mark.parametrize("value", ["TRACE", "", "info "])
def test_log_level_is_validated(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level=value)


def test_log_level_and_format_are_normalized():
    settings = Settings(_env_file=None, log_level="warning", log_format="JSON")

    assert settings.log_level == "WARNING"
    assert settings.log_format == "json"


def test_log_format_is_validated():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_format="file")


def test_setup_logger_is_idempotent_and_emits_one_record(
    monkeypatch, isolated_prez_logger
):
    output = io.StringIO()
    monkeypatch.setattr("prez.services.prez_logging.sys.stdout", output)
    settings = Settings(
        _env_file=None,
        log_level="INFO",
        log_format="json",
        prez_version="9.8.7",
    )

    setup_logger(settings)
    setup_logger(settings)
    get_logger("prez.test.logging").info("Completed", extra={"item.count": 2})

    lines = output.getvalue().splitlines()
    assert len(isolated_prez_logger.handlers) == 1
    assert len(lines) == 1
    assert json.loads(lines[0])["attributes"]["item.count"] == 2


def test_request_completion_has_typed_fields_and_timing_breakdown():
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
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        with TestClient(app) as client:
            assert client.get("/timed?limit=1").status_code == 200
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    completion = next(
        record
        for record in records
        if getattr(record, "event.name", None) == "request.complete"
    )
    assert completion.getMessage() == "Request completed"
    assert completion.levelno == logging.INFO
    assert getattr(completion, "http.request.method") == "GET"
    assert getattr(completion, "http.response.status_code") == 200
    assert getattr(completion, "url.path") == "/timed"
    assert completion.query_string_size_bytes == len(b"limit=1")
    assert completion.response_body_chunk_count >= 1
    assert isinstance(completion.response_size_bytes, int)
    assert isinstance(completion.duration_ms, float)
    assert completion.downstream_duration_ms > 0
    assert completion.prez_duration_ms >= 0
    assert completion.duration_ms == pytest.approx(
        completion.downstream_duration_ms + completion.prez_duration_ms, abs=0.2
    )


def test_downstream_timing_merges_concurrent_waits():
    assert _union_duration_ms([(1.0, 1.010), (1.005, 1.020)]) == pytest.approx(20.0)

    token = bind_downstream_timings()
    try:
        record_downstream_timing(1.0, 1.01)
        assert get_downstream_timing_spans() == [(1.0, 1.01)]
    finally:
        reset_downstream_timings(token)


@pytest.mark.asyncio
async def test_sparql_proxy_does_not_forward_x_request_id_and_tracks_wait(monkeypatch):
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
            response = await repo.sparql(
                "SELECT * WHERE {}",
                [(b"x-request-id", b"do-not-forward"), (b"x-client", b"retained")],
            )
            await response.aread()
            assert get_downstream_timing_spans()
        finally:
            reset_downstream_timings(token)

    assert "x-request-id" not in received
    assert received["x-client"] == "retained"


@pytest.mark.asyncio
async def test_remote_sparql_error_does_not_embed_response_body_in_exception(
    monkeypatch,
):
    secret_body = b"query=SELECT * WHERE {} password=do-not-log"

    def respond(request: httpx.Request):
        return httpx.Response(400, content=secret_body)

    monkeypatch.setattr(
        "prez.repositories.remote_sparql.settings.sparql_endpoint",
        "http://example.test/sparql",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        repo = RemoteSparqlRepo(client)
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await repo._send_query("SELECT * WHERE {}")

    assert secret_body.decode() not in str(exc_info.value)
    assert "do-not-log" not in str(exc_info.value)
    # Preserve the response for the existing HTTP error handler without copying its
    # unbounded contents into exception serialization.
    assert exc_info.value.response.text == secret_body.decode()
