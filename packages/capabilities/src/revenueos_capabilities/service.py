"""Capability registry (V1A-4) + retained V1A-3 stub interface.

The real registry is backed by ``provider_capabilities``. A capability is
usable only when it is registered, enabled, and explicitly VERIFIED. Nothing
is ever fabricated as usable; an unknown capability is DENIED, not allowed.

The V1A-3 ``*_stub`` helpers are kept so the recorded-only hook-point remains
available and its deny-by-default contract is unchanged. The production entry
point is :func:`capability_guard`.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_capabilities.models import (
    ProviderCapability,
    VERIFICATION_VERIFIED,
)

GUARD_ALLOWED = "ALLOWED"
GUARD_DENIED = "DENIED"
GUARD_UNVERIFIED = "UNVERIFIED"
GUARD_NOT_APPLICABLE = "NOT_APPLICABLE"


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


# --------------------------------------------------------------------------
# production registry (V1A-4)
# --------------------------------------------------------------------------
def register_capability(
    db: DbSession,
    *,
    provider_id: str,
    capability_id: str,
    verification_state: str = "UNVERIFIED",
    enabled: bool = False,
    scope: dict | None = None,
    notes: str | None = None,
) -> ProviderCapability:
    """Register or update a capability. Upsert keyed by ``capability_id``.

    ``verification_state`` defaults to UNVERIFIED and ``enabled`` to False:
    registration alone never makes a capability usable.
    """
    if not provider_id or not capability_id:
        raise ValueError("provider_id and capability_id are required")
    row = db.execute(
        select(ProviderCapability).where(ProviderCapability.capability_id == capability_id)
    ).scalar_one_or_none()
    if row is None:
        import uuid as _uuid

        row = ProviderCapability(
            id=_uuid.uuid4().hex,
            provider_id=provider_id,
            capability_id=capability_id,
            verification_state=verification_state,
            enabled=enabled,
            scope_json=scope,
            notes=notes,
        )
        db.add(row)
    else:
        row.provider_id = provider_id
        row.verification_state = verification_state
        row.enabled = enabled
        row.scope_json = scope
        row.notes = notes
    db.flush()
    return row


def lookup(db: DbSession, capability_id: str) -> ProviderCapability | None:
    if not capability_id:
        return None
    return db.execute(
        select(ProviderCapability).where(ProviderCapability.capability_id == capability_id)
    ).scalar_one_or_none()


def is_within_scope(cap: ProviderCapability, unit: str | None, amount: str | None) -> bool:
    """True only when a VERIFIED/enabled capability's scope permits the request.

    An empty scope means "no additional constraint". A populated scope must
    name the unit and (if a max_amount is given) the request must not exceed it.
    """
    scope = cap.scope_json or {}
    allowed_units = scope.get("units")
    if allowed_units:
        if unit is None or unit not in allowed_units:
            return False
    max_amount = scope.get("max_amount")
    if max_amount is not None and amount is not None:
        try:
            if Decimal(str(amount)) > Decimal(str(max_amount)):
                return False
        except (InvalidOperation, ValueError):
            return False
    return True


def capability_guard(
    db: DbSession,
    capability_id: str,
    *,
    unit: str | None = None,
    amount: str | None = None,
) -> tuple[str, str]:
    """Deny-by-default evaluation of a capability reference.

    Returns ``(state, reason)`` where state is ALLOWED or DENIED. There is no
    UNVERIFIED-usable outcome: an unverified capability is DENIED.
    """
    cap = lookup(db, capability_id)
    if cap is None:
        return GUARD_DENIED, f"capability {capability_id!r} is not registered"
    if not cap.enabled:
        return GUARD_DENIED, f"capability {capability_id!r} is disabled"
    if cap.verification_state != VERIFICATION_VERIFIED:
        return (
            GUARD_DENIED,
            f"capability {capability_id!r} is {cap.verification_state}, not VERIFIED",
        )
    if not is_within_scope(cap, unit, amount):
        return GUARD_DENIED, f"capability {capability_id!r} scope does not permit the request"
    return GUARD_ALLOWED, f"capability {capability_id!r} is VERIFIED and within scope"
