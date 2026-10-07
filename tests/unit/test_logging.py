"""Structured logging unit tests."""

import json
import logging

import pytest

from revenueos_shared.config import Settings
from revenueos_shared.logging import (
    JsonFormatter,
    correlation_id_var,
    configure_logging,
    get_correlation_id,
    set_correlation_id,
)

pytestmark = pytest.mark.unit


def _record(message="hello world"):
    return logging.LogRecord(
        "revenueos.test", logging.INFO, "test.py", 1, message, None, None
    )


def test_json_formatter_produces_valid_json_with_required_fields():
    payload = json.loads(JsonFormatter().format(_record()))
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "revenueos.test"
    assert "time" in payload
    assert "correlation_id" in payload
    assert "service" in payload
    assert "environment" in payload


def test_json_formatter_includes_extra_fields():
    record = _record()
    record.component = "api"
    record.status = "ready"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["component"] == "api"
    assert payload["status"] == "ready"


def test_correlation_contextvar_roundtrip():
    previous = correlation_id_var.get()
    try:
        cid = set_correlation_id("abc123")
        assert cid == "abc123"
        assert get_correlation_id() == "abc123"
        generated = set_correlation_id()
        assert len(generated) == 32
    finally:
        correlation_id_var.set(previous)


def test_configure_logging_installs_json_handler():
    settings = Settings(_env_file=None, log_format="json")
    configure_logging(settings, service="unit-test")
    root = logging.getLogger()
    assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
    assert root.level == logging.INFO
