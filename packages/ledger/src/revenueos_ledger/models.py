"""Financial core ORM models (V1A-2).

Append-only: journal entries and lines are immutable (enforced by service
rules AND database triggers). Accounts are retired via status=CLOSED,
never deleted.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from revenueos_shared.db import Base

ACCOUNT_KINDS = ("ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE")
SIDES = ("DEBIT", "CREDIT")
NORMAL_BALANCE_BY_KIND = {
    "ASSET": "DEBIT",
    "EXPENSE": "DEBIT",
    "LIABILITY": "CREDIT",
    "EQUITY": "CREDIT",
    "REVENUE": "CREDIT",
}
ACCOUNT_STATUS_ACTIVE = "ACTIVE"
ACCOUNT_STATUS_CLOSED = "CLOSED"

MONEY_PRECISION = 20
MONEY_SCALE = 6


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_ledger_accounts_tenant_code"),
        CheckConstraint(
            "kind IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')",
            name="ck_ledger_accounts_kind",
        ),
        CheckConstraint(
            "normal_balance IN ('DEBIT','CREDIT')", name="ck_ledger_accounts_normal"
        ),
        CheckConstraint("length(currency) = 3", name="ck_ledger_accounts_currency"),
        CheckConstraint(
            "status IN ('ACTIVE','CLOSED')", name="ck_ledger_accounts_status"
        ),
        Index("ix_ledger_accounts_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    normal_balance: Mapped[str] = mapped_column(String(6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ACCOUNT_STATUS_ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LedgerJournalEntry(Base):
    __tablename__ = "ledger_journal_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_journal_entries_tenant_idem"
        ),
        CheckConstraint("length(currency) = 3", name="ck_journal_entries_currency"),
        Index("ix_journal_entries_tenant_posted", "tenant_id", "posted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list["LedgerJournalLine"]] = relationship(
        "LedgerJournalLine",
        back_populates="entry",
        order_by="LedgerJournalLine.line_number",
        lazy="selectin",
    )


class LedgerJournalLine(Base):
    __tablename__ = "ledger_journal_lines"
    __table_args__ = (
        UniqueConstraint(
            "entry_id", "line_number", name="uq_journal_lines_entry_line"
        ),
        CheckConstraint("side IN ('DEBIT','CREDIT')", name="ck_journal_lines_side"),
        CheckConstraint("amount > 0", name="ck_journal_lines_amount_positive"),
        CheckConstraint("length(currency) = 3", name="ck_journal_lines_currency"),
        Index("ix_journal_lines_account_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entry_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ledger_journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ledger_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    side: Mapped[str] = mapped_column(String(6), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    entry: Mapped[LedgerJournalEntry] = relationship(
        "LedgerJournalEntry", back_populates="lines"
    )


class ProviderUsageEvent(Base):
    __tablename__ = "provider_usage_event"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider_id", "idempotency_key",
            name="uq_provider_usage_tenant_provider_idem",
        ),
        CheckConstraint("quantity > 0", name="ck_provider_usage_quantity_positive"),
        Index("ix_provider_usage_tenant_provider", "tenant_id", "provider_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProviderCostEvent(Base):
    __tablename__ = "provider_cost_event"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider_id", "idempotency_key",
            name="uq_provider_cost_tenant_provider_idem",
        ),
        CheckConstraint("amount > 0", name="ck_provider_cost_amount_positive"),
        CheckConstraint("length(currency) = 3", name="ck_provider_cost_currency"),
        Index("ix_provider_cost_tenant_provider", "tenant_id", "provider_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cost_type: Mapped[str] = mapped_column(String(64), nullable=False)
    usage_event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_usage_event.id", ondelete="RESTRICT"),
        nullable=True,
    )
    journal_entry_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ledger_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
