"""Capability registry stubs (V1A-3).

Capabilities are UNVERIFIED. The real provider capability model is deferred.
This package's role is to reserve the interface the ExecutionController uses
to look up whether a proposed effect is within capability scope.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityStub:
    capability_id: str
    provider_id: str
    state: str = "UNVERIFIED"
    scope: str = "UNVERIFIED"


def lookup_stub(capability_id: str) -> CapabilityStub | None:
    """Stub lookup. Real capability lookup is not implemented."""
    return None


def is_within_scope_stub(capability_id: str, requested_unit: str, requested_amount: str) -> bool:
    """Deny-by-default stub. No capability is within scope until verified."""
    return False
