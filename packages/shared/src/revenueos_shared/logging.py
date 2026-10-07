"""Structured JSON logging with correlation-id injection (stdlib only)."""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

_service_info = {"service": "unknown", "environment": "unknown"}

_STD_RECORD_KEYS = (
    "event",
    "component",
    "status",
    "detail",
    "check",
    "latency_ms",
    "task",
    "correlation_id",
)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def set_correlation_id(value: str | None = None) -> str:
    cid = value or new_correlation_id()
    correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> str:
    return correlation_id_var.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": _service_info["service"],
            "environment": _service_info["environment"],
            "correlation_id": getattr(record, "correlation_id", None) or correlation_id_var.get(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _STD_RECORD_KEYS:
            if key == "correlation_id":
                continue
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        cid = getattr(record, "correlation_id", None) or correlation_id_var.get()
        base = f"{self.formatTime(record)} {record.levelname} [{cid}] {record.name}: {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(settings, service: str) -> None:
    """Install the process logging configuration. Safe to call more than once."""
    _service_info["service"] = service
    _service_info["environment"] = settings.environment

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            PlainFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Our log records are the structured source of truth; keep uvicorn's
    # access logger quiet in JSON mode to avoid unstructured duplication.
    if settings.log_format.lower() == "json":
        logging.getLogger("uvicorn.access").propagate = False
