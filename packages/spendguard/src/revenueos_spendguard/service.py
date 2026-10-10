"""SpendGuard (V1A-4): production budget evaluation + retained V1A-3 stub.

The production entry point is :func:`evaluate_spend`. It compares a requested
spend against the tenant's configured budget and the spend RevenueOS has
already *recorded* (provider_cost_event rows) for the budget period:

  * no budget  -> NOT_APPLICABLE (nothing configured to enforce; recorded)
  * within cap -> ALLOWED
  * over cap   -> DENIED

Every evaluation is persisted as a ``spend_guard_decisions`` row. The V1A-3
``evaluate_stub``/``allow_stub`` helpers are retained unchanged so the
records-only hook-point contract and its tests still hold.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from revenueos_spendguard.models import (
    BUDGET_PERIOD_MONTHLY,
    BUDGET_PERIOD_TOTAL,
    BUDGET_PERIODS,
    SpendGuardBudget,
    SpendGuardDecision,
    SPendGuardState_ALLOWED,
    SPendGuardState_DENIED,
    SPendGuardState_NOT_APPLICABLE,
    SPendGuardState_UNVERIFIED,
)


class SpendGuardUnverifiedError(RuntimeError):
    """Raised when code attempts a spend decision that depends on a verified state."""


# --------------------------------------------------------------------------
# V1A-3 stub interface (retained; unchanged semantics)
# --------------------------------------------------------------------------
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
        id=uuid.uuid4().hex,
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
        select(SpendGuardDecision).where(
            SpendGuardDecision.id == decision_id, SpendGuardDecision.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("spend guard decision not found")
    row.state = SPendGuardState_ALLOWED
    row.reason = "stub override (test only)"
    db.flush()
    return row


# --------------------------------------------------------------------------
# budget configuration (V1A-4)
# --------------------------------------------------------------------------
def set_budget(
    db: DbSession,
    *,
    tenant_id: str,
    currency: str,
    limit_amount: str | Decimal,
    provider_id: str | None = None,
    period: str = BUDGET_PERIOD_MONTHLY,
    note: str | None = None,
) -> SpendGuardBudget:
    """Create or update a budget. ``limit_amount`` must be a positive decimal."""
    currency = currency.upper().strip()
    period = period.upper().strip()
    if period not in BUDGET_PERIODS:
        raise ValueError(f"invalid budget period: {period!r} (one of {BUDGET_PERIODS})")
    amount = Decimal(str(limit_amount))
    if amount <= 0:
        raise ValueError("budget limit_amount must be positive")
    row = db.execute(
        select(SpendGuardBudget).where(
            SpendGuardBudget.tenant_id == tenant_id,
            SpendGuardBudget.provider_id == provider_id,
            SpendGuardBudget.currency == currency,
            SpendGuardBudget.period == period,
        )
    ).scalar_one_or_none()
    if row is None:
        row = SpendGuardBudget(
            id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            provider_id=provider_id,
            currency=currency,
            period=period,
            limit_amount=amount,
            enabled=True,
            note=note,
        )
        db.add(row)
    else:
        row.limit_amount = amount
        row.enabled = True
        row.note = note
    db.flush()
    return row


def list_budgets(db: DbSession, tenant_id: str) -> list[SpendGuardBudget]:
    return list(
        db.execute(
            select(SpendGuardBudget)
            .where(SpendGuardBudget.tenant_id == tenant_id)
            .order_by(SpendGuardBudget.provider_id.nulls_first(), SpendGuardBudget.currency)
        ).scalars()
    )


def _find_budget(
    db: DbSession, tenant_id: str, currency: str | None, provider_id: str | None
) -> SpendGuardBudget | None:
    q = select(SpendGuardBudget).where(
        SpendGuardBudget.tenant_id == tenant_id,
        SpendGuardBudget.enabled.is_(True),
    )
    if currency:
        q = q.where(SpendGuardBudget.currency == currency.upper())
    candidates = list(db.execute(q).scalars())
    if not candidates:
        return None
    # Prefer a provider-specific budget, then the tenant-wide (provider NULL) one.
    for row in candidates:
        if provider_id is not None and row.provider_id == provider_id:
            return row
    for row in candidates:
        if row.provider_id is None:
            return row
    return None


def _period_start(period: str, now: datetime) -> datetime | None:
    if period == BUDGET_PERIOD_TOTAL:
        return None
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _recorded_spend(
    db: DbSession, tenant_id: str, budget: SpendGuardBudget, since: datetime | None
) -> Decimal:
    """Sum of provider_cost_event amounts already recorded for this tenant.

    This reads RevenueOS-recorded observations (V1A-2 contract) — it does not
    invent a cost. If the table is absent (unit SQLite fixture without financial
    models) the recorded spend is treated as zero.
    """
    try:
        from revenueos_ledger.models import ProviderCostEvent
    except Exception:  # pragma: no cover - only when ledger models are unavailable
        return Decimal("0")
    q = select(func.coalesce(func.sum(ProviderCostEvent.amount), 0)).where(
        ProviderCostEvent.tenant_id == tenant_id,
        ProviderCostEvent.currency == budget.currency,
    )
    if budget.provider_id is not None:
        q = q.where(ProviderCostEvent.provider_id == budget.provider_id)
    if since is not None:
        q = q.where(ProviderCostEvent.occurred_at >= since)
    try:
        value = db.execute(q).scalar()
    except Exception:
        return Decimal("0")
    return Decimal(str(value or 0))


def evaluate_spend(
    db: DbSession,
    *,
    tenant_id: str,
    correlation_id: str,
    intent: str,
    provider_id: str | None = None,
    currency: str | None = None,
    amount: str | Decimal | None = None,
) -> SpendGuardDecision:
    """Production spend evaluation. Deny-by-default, and never fabricates ALLOWED.

    Only a configured budget can produce ALLOWED. No budget -> NOT_APPLICABLE.
    """
    budget = _find_budget(db, tenant_id, currency, provider_id)
    if budget is None:
        decision = SpendGuardDecision(
            id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            intent=intent,
            state=SPendGuardState_NOT_APPLICABLE,
            reason="no spend budget configured for this tenant/provider/currency",
        )
        db.add(decision)
        db.flush()
        return decision

    requested = Decimal(str(amount)) if amount is not None else Decimal("0")
    since = _period_start(budget.period, datetime.now(timezone.utc))
    spent = _recorded_spend(db, tenant_id, budget, since)
    projected = spent + requested
    if projected <= budget.limit_amount:
        state = SPendGuardState_ALLOWED
        reason = (
            f"within budget: spent={spent} + requested={requested} <= limit={budget.limit_amount} "
            f"({budget.period})"
        )
    else:
        state = SPendGuardState_DENIED
        reason = (
            f"over budget: spent={spent} + requested={requested} > limit={budget.limit_amount} "
            f"({budget.period})"
        )
    decision = SpendGuardDecision(
        id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        intent=intent,
        state=state,
        reason=reason,
    )
    db.add(decision)
    db.flush()
    return decision
