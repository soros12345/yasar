"""Correlation ID middleware unit tests (pure ASGI, no server required)."""

import asyncio

import pytest

from revenueos_shared.correlation import CorrelationIdMiddleware, correlation_id_dependency

pytestmark = pytest.mark.unit


class _FakeApp:
    def __init__(self):
        self.seen_correlation_id = None

    async def __call__(self, scope, receive, send):
        self.seen_correlation_id = correlation_id_dependency()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})


def _run(headers: dict[str, str]):
    app = _FakeApp()
    middleware = CorrelationIdMiddleware(app)
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/health",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    asyncio.run(middleware(scope, receive, send))
    return app, messages


def test_generates_correlation_id_when_absent():
    app, messages = _run({})
    start = messages[0]
    response_headers = {
        k.decode("latin-1").lower(): v.decode("latin-1") for k, v in start["headers"]
    }
    cid = response_headers.get("x-correlation-id")
    assert cid and len(cid) == 32
    assert app.seen_correlation_id == cid


def test_propagates_incoming_correlation_id():
    app, messages = _run({"x-correlation-id": "trace-abc-42"})
    start = messages[0]
    response_headers = {
        k.decode("latin-1").lower(): v.decode("latin-1") for k, v in start["headers"]
    }
    assert response_headers.get("x-correlation-id") == "trace-abc-42"
    assert app.seen_correlation_id == "trace-abc-42"
