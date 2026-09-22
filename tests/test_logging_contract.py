import io
import json
import logging
import sys

import pytest
from pydantic import ValidationError

from prez.config import Settings
from prez.services.prez_logging import (
    _ConsoleFormatter,
    _JsonFormatter,
    get_logger,
    setup_logger,
)


def test_get_logger_returns_standard_logger():
    assert type(get_logger("prez.test.contract")) is logging.Logger


def test_json_formatter_preserves_typed_flat_extras_and_exception():
    formatter = _JsonFormatter("1.2.3")
    try:
        raise RuntimeError("formatting failed")
    except RuntimeError:
        record = logging.LogRecord(
            "prez.test.contract",
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

    assert "\n" not in line
    assert payload["timestamp"].endswith("Z")
    assert payload["severity_text"] == "ERROR"
    assert payload["body"] == "Request failed with value=7"
    assert payload["logger.name"] == "prez.test.contract"
    assert payload["attributes"] == {
        "event.name": "request.failed",
        "duration_ms": 1.25,
        "cached": False,
        "optional": None,
    }
    assert "RuntimeError: formatting failed" in payload["exception"]
    assert payload["resource"] == {
        "service.name": "prez",
        "service.version": "1.2.3",
    }


def test_console_formatter_does_not_parse_message_fields():
    record = logging.LogRecord(
        "prez.test.contract",
        logging.INFO,
        __file__,
        1,
        "URL ?limit=10 enabled=true",
        (),
        None,
    )
    record.__dict__["result.count"] = 3

    output = _ConsoleFormatter().format(record)

    assert "URL ?limit=10 enabled=true" in output
    assert "result.count=3" in output


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


def test_setup_logger_is_idempotent_and_writes_one_json_line(monkeypatch):
    output = io.StringIO()
    monkeypatch.setattr("prez.services.prez_logging.sys.stdout", output)
    logger = logging.getLogger("prez")
    previous_handlers = logger.handlers[:]
    previous_level = logger.level
    previous_propagate = logger.propagate
    try:
        settings = Settings(
            _env_file=None,
            log_level="INFO",
            log_format="json",
            prez_version="9.8.7",
        )
        setup_logger(settings)
        setup_logger(settings)
        get_logger("prez.test.contract").info("Completed", extra={"item.count": 2})

        lines = output.getvalue().splitlines()
        assert len(logger.handlers) == 1
        assert len(lines) == 1
        assert json.loads(lines[0])["attributes"]["item.count"] == 2
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
