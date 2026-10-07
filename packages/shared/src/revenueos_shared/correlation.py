"""Correlation ID ASGI middleware (framework-agnostic, no third-party deps)."""

import uuid
from collections.abc import Awaitable, Callable

from revenueos_shared.logging import correlation_id_var

CORRELATION_HEADER = b"x-correlation-id"


class CorrelationIdMiddleware:
    """Assigns/propagates X-Correlation-ID for every HTTP request."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        cid = headers.get("x-correlation-id") or uuid.uuid4().hex
        token = correlation_id_var.set(cid)

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                raw_headers.append((CORRELATION_HEADER, cid.encode("latin-1")))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            correlation_id_var.reset(token)


def correlation_id_dependency() -> str:
    """FastAPI dependency returning the current request correlation id."""
    return correlation_id_var.get()
