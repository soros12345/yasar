"""Execution policy engine (V1A-4).

Every intent must be permitted by an explicit tenant policy, except the three
RevenueOS-internal intents (ledger post, provider-event ingest, outbox flush),
which are allowed by default because they are internal effects, not external
provider calls. Anything else — including any provider-adapter intent — is
DENY-by-default until a policy row grants it.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from revenueos_shared.db import Base

GUARD_ALLOWED = "ALLOWED"
GUARD_DENIED = "DENIED"
GUARD_NOT_APPLICABLE = "NOT_APPLICABLE"

EFFECT_ALLOW = "ALLOW"
EFFECT_DENY = "DENY"

# Internal effects: RevenueOS-owned, no external provider authority required.
INTERNAL_INTENTS = ("post_journal_entry", "ingest_provider_event", "outbox_flush")


class ExecutionPolicy(Base):
    __tablename__ = "execution_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    effect: Mapped[str] = mapped_column(String(16), nullable=False, default=EFFECT_DENY)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "intent", name="uq_execution_policy_tenant_intent"),
        Index("ix_execution_policies_tenant", "tenant_id"),
    )


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------
def set_policy(
    db,
    *,
    tenant_id: str,
    intent: str,
    effect: str = EFFECT_DENY,
    requires_approval: bool = False,
    note: str | None = None,
):
    """Create or update a tenant policy for an intent. Upsert by (tenant, intent)."""
    from sqlalchemy import select

    effect = effect.upper().strip()
    if effect not in (EFFECT_ALLOW, EFFECT_DENY):
        raise ValueError(f"invalid policy effect: {effect!r}")
    row = db.execute(
        select(ExecutionPolicy).where(
            ExecutionPolicy.tenant_id == tenant_id, ExecutionPolicy.intent == intent
        )
    ).scalar_one_or_none()
    if row is None:
        import uuid as _uuid

        row = ExecutionPolicy(
            id=_uuid.uuid4().hex,
            tenant_id=tenant_id,
            intent=intent,
            effect=effect,
            requires_approval=requires_approval,
            enabled=True,
            note=note,
        )
        db.add(row)
    else:
        row.effect = effect
        row.requires_approval = requires_approval
        row.enabled = True
        row.note = note
    db.flush()
    return row


def _find_policy(db, tenant_id: str, intent: str):
    from sqlalchemy import select

    return db.execute(
        select(ExecutionPolicy).where(
            ExecutionPolicy.tenant_id == tenant_id,
            ExecutionPolicy.intent == intent,
            ExecutionPolicy.enabled.is_(True),
        )
    ).scalar_one_or_none()


def evaluate_policy(db, tenant_id: str, intent: str) -> tuple[str, bool, str]:
    """Return ``(state, requires_approval, reason)``.

    An explicit enabled policy wins. Otherwise internal intents are ALLOWED
    (no approval) and every other intent is DENIED (approval required).
    """
    row = _find_policy(db, tenant_id, intent)
    if row is not None:
        if row.effect == EFFECT_ALLOW:
            return GUARD_ALLOWED, row.requires_approval, f"policy ALLOW for {intent!r}"
        return GUARD_DENIED, row.requires_approval, f"policy DENY for {intent!r}"
    if intent in INTERNAL_INTENTS:
        return GUARD_ALLOWED, False, f"internal intent {intent!r} allowed by default"
    return GUARD_DENIED, True, f"no policy grants intent {intent!r} (deny-by-default)"


def list_policies(db, tenant_id: str):
    from sqlalchemy import select

    return list(
        db.execute(
            select(ExecutionPolicy)
            .where(ExecutionPolicy.tenant_id == tenant_id)
            .order_by(ExecutionPolicy.intent)
        ).scalars()
    )
