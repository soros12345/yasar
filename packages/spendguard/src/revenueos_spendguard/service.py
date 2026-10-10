"""SpendGuard enforcement stubs — deny-by-default, UNVERIFIED.

Real spend evaluation is not implemented in V1A-3. The hook-point exists so
the ExecutionController can call it; today it records UNVERIFIED and denies
anything that would rely on a verified spend decision.
"""

from sqlalchemy.orm import Session as DbSession

from revenueos_spendguard.models import (
    SpendGuardDecision,
    SPendGuardState_ALLOWED,
    SPendGuardState_DENIED,
    SPendGuardState_UNVERIFIED,
)


class SpendGuardUnverifiedError(RuntimeError):
    """Raised when code attempts a spend decision that depends on a verified state."""


def evaluate_stub(
    db: DbSession,
    *,
    tenant_id: str,
    correlation_id: str,
    intent: str,
    deny: bool = False,
) -> SpendGuardDecision:
    """Deny-by-default stub. No spend decision can ever be fabricated as ALLOWED
    here: with ``deny=False`` the state is recorded as UNVERIFIED (the honest
    "authority not yet implemented" state) and callers that require a verified
    spend decision must refuse to proceed. ``deny=True`` records the explicit
    DENIED branch so the denial path is exercised end-to-end.
    """
    state = SPendGuardState_DENIED if deny else SPendGuardState_UNVERIFIED
    reason = (
        "SpendGuard denied by stub (deny=True)"
        if deny
        else "SpendGuard is stubbed and UNVERIFIED in V1A-3"
    )
    decision = SpendGuardDecision(
        id=__import__("uuid").uuid4().hex,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        intent=intent,
        state=state,
        reason=reason,
    )
    db.add(decision)
    db.flush()
    return decision


def allow_stub(db: DbSession, decision_id: str, tenant_id: str) -> SpendGuardDecision:
    """Test-only escape hatch to mark a stubbed decision ALLOWED. Never used in
    production code paths."""
    row = db.execute(
        __import__("sqlalchemy").select(SpendGuardDecision).where(
            SpendGuardDecision.id == decision_id, SpendGuardDecision.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("spend guard decision not found")
    row.state = SPendGuardState_ALLOWED
    row.reason = "stub override (test only)"
    db.flush()
    return row
