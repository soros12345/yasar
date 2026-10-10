"""Provider adapter framework (V1A-4).

A provider adapter is the *only* place an external provider call can happen,
and it may only run when its capability is registered, enabled, and VERIFIED.
The default registry contains the Awin publisher adapter in a DISABLED state:
no Awin capability has been verified, so an attempt to invoke it is denied
before any transport is touched.

Transports are pluggable. ``LocalTransport`` runs in-process (used to exercise
the adapter boundary in tests without any network); ``HttpTransport`` is the
production transport and is only reachable for a VERIFIED, enabled adapter.
"""
from dataclasses import dataclass, field
from typing import Protocol

from revenueos_capabilities.service import GUARD_ALLOWED, capability_guard


class AdapterError(RuntimeError):
    """Raised for an unknown adapter or an invalid invocation."""


class AdapterDeniedError(AdapterError):
    """Raised when the capability gate refuses an invocation."""


@dataclass
class AdapterResult:
    adapter_id: str
    capability_id: str
    operation: str
    status: str
    detail: str
    response: dict | None = None


class Transport(Protocol):
    def send(self, adapter_id: str, operation: str, params: dict) -> dict: ...


class LocalTransport:
    """In-process transport: records calls and echoes the request. No network."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send(self, adapter_id: str, operation: str, params: dict) -> dict:
        record = {"adapter_id": adapter_id, "operation": operation, "params": params}
        self.calls.append(record)
        return {"echo": record}


class HttpTransport:
    """Production HTTP transport. Lazily imports httpx; never used by default."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        if not base_url:
            raise AdapterError("HttpTransport requires a base_url")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def send(self, adapter_id: str, operation: str, params: dict) -> dict:
        import httpx  # imported lazily so in-process paths need no HTTP stack

        resp = httpx.post(
            f"{self.base_url}/{operation}",
            json={"params": params},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"text": resp.text}


class ProviderAdapter:
    """Base class for provider adapters. Disabled unless explicitly enabled."""

    adapter_id: str = ""
    capability_id: str = ""
    enabled: bool = False
    transport: Transport | None = None

    def invoke(self, transport: Transport, operation: str, params: dict) -> dict:
        raise NotImplementedError


class AwinPublisherAdapter(ProviderAdapter):
    """Awin publisher connector adapter — DISABLED.

    Awin publisher credentials/capabilities are UNVERIFIED (provider-manifest),
    so no operation may be dispatched. This class documents the boundary; it
    performs no network call.
    """

    adapter_id = "awin_publisher"
    capability_id = "awin_publisher_redirect"
    enabled = False

    def invoke(self, transport: Transport, operation: str, params: dict) -> dict:
        raise AdapterDeniedError(
            "awin_publisher adapter is disabled: no Awin capability is VERIFIED"
        )


_REGISTRY: dict[str, ProviderAdapter] = {}


def register_adapter(adapter: ProviderAdapter) -> ProviderAdapter:
    if not adapter.adapter_id:
        raise AdapterError("adapter must declare an adapter_id")
    _REGISTRY[adapter.adapter_id] = adapter
    return adapter


def get_adapter(adapter_id: str) -> ProviderAdapter | None:
    return _REGISTRY.get(adapter_id)


def list_adapters() -> list[ProviderAdapter]:
    return sorted(_REGISTRY.values(), key=lambda a: a.adapter_id)


def invoke_adapter(
    db,
    *,
    adapter_id: str,
    operation: str,
    params: dict | None = None,
    capability_id: str | None = None,
    unit: str | None = None,
    amount: str | None = None,
    transport: Transport | None = None,
) -> AdapterResult:
    """Capability-gated adapter invocation.

    The capability gate runs first; an unverified capability denies the call
    before the adapter or transport is consulted.
    """
    adapter = get_adapter(adapter_id)
    if adapter is None:
        raise AdapterError(f"unknown adapter: {adapter_id!r}")
    cap_id = capability_id or adapter.capability_id
    state, reason = capability_guard(db, cap_id, unit=unit, amount=amount)
    if state != GUARD_ALLOWED:
        raise AdapterDeniedError(f"capability gate denied {adapter_id!r}: {reason}")
    if not adapter.enabled:
        raise AdapterDeniedError(f"adapter {adapter_id!r} is not enabled")
    active_transport = transport or adapter.transport
    if active_transport is None:
        raise AdapterError(f"adapter {adapter_id!r} has no transport configured")
    response = adapter.invoke(active_transport, operation, params or {})
    return AdapterResult(
        adapter_id=adapter_id,
        capability_id=cap_id,
        operation=operation,
        status="DISPATCHED",
        detail=reason,
        response=response,
    )


register_adapter(AwinPublisherAdapter())
