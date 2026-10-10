"""SpendGuard models (V1A-4): decisions + per-tenant spend budgets.

SpendGuard is deny-by-default. A spend is allowed only when an explicit budget
exists and the ledger-recorded provider spend for the period stays within it.
Without a configured budget, the guard reports NOT_APPLICABLE (nothing to
enforce) and records that fact for audit — it never fabricates an ALLOWED.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from revenueos_shared.db import Base

SPendGuardState_UNVERIFIED = "UNVERIFIED"
SPendGuardState_DENIED = "DENIED"
SPendGuardState_ALLOWED = "ALLOWED"
SPendGuardState_DEFERRED = "DEFERRED"
SPendGuardState_NOT_APPLICABLE = "NOT_APPLICABLE"

MONEY_PRECISION = 24
MONEY_SCALE = 8

BUDGET_PERIOD_MONTHLY = "MONTHLY"
BUDGET_PERIOD_TOTAL = "TOTAL"
BUDGET_PERIODS = (BUDGET_PERIOD_MONTHLY, BUDGET_PERIOD_TOTAL)


class SpendGuardDecision(Base):
    __tablename__ = "spend_guard_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SPendGuardState_UNVERIFIED
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_spendguard_tenant_state", "tenant_id", "state"),
        Index("ix_spendguard_correlation", "correlation_id"),
    )


class SpendGuardBudget(Base):
    __tablename__ = "spend_guard_budgets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # NULL provider_id means "any provider for this tenant".
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default=BUDGET_PERIOD_MONTHLY)
    limit_amount: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider_id", "currency", "period",
            name="uq_spend_budget_tenant_provider_currency_period",
        ),
        Index("ix_spend_budgets_tenant", "tenant_id"),
    )
