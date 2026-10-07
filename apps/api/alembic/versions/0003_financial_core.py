"""V1A-2 financial core (empty-safe, reversible).

Revision ID: 0003_financial_core
Revises: 0002_multitenant_security
Create Date: 2026-10-07

ledger_accounts, ledger_journal_entries, ledger_journal_lines,
provider_usage_event, provider_cost_event + append-only DB triggers.

Immutability escape hatch: session GUC `revenueos.allow_ledger_purge = 'on'`
permits controlled purge (test fixtures / operator recovery only).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_financial_core"
down_revision: Union[str, None] = "0002_multitenant_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APPEND_ONLY_FUNCTION = """
CREATE OR REPLACE FUNCTION revenueos_ledger_append_only() RETURNS trigger AS $$
BEGIN
  IF current_setting('revenueos.allow_ledger_purge', true) = 'on' THEN
    RETURN NULL;  -- controlled purge path (never used in normal operation)
  END IF;
  RAISE EXCEPTION
    'RevenueOS ledger is append-only: % on % is forbidden', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql
"""

DROP_FUNCTION = "DROP FUNCTION IF EXISTS revenueos_ledger_append_only()"


def upgrade() -> None:
    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("normal_balance", sa.String(length=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')", name="ck_ledger_accounts_kind"),
        sa.CheckConstraint("normal_balance IN ('DEBIT','CREDIT')", name="ck_ledger_accounts_normal"),
        sa.CheckConstraint("length(currency) = 3", name="ck_ledger_accounts_currency"),
        sa.CheckConstraint("status IN ('ACTIVE','CLOSED')", name="ck_ledger_accounts_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_ledger_accounts_tenant_code"),
    )
    op.create_index("ix_ledger_accounts_tenant_id", "ledger_accounts", ["tenant_id"])

    op.create_table(
        "ledger_journal_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(currency) = 3", name="ck_journal_entries_currency"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_journal_entries_tenant_idem"),
    )
    op.create_index("ix_journal_entries_tenant_posted", "ledger_journal_entries", ["tenant_id", "posted_at"])

    op.create_table(
        "ledger_journal_lines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entry_id", sa.String(length=36), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("side", sa.String(length=6), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_journal_lines_amount_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_journal_lines_currency"),
        sa.CheckConstraint("side IN ('DEBIT','CREDIT')", name="ck_journal_lines_side"),
        sa.ForeignKeyConstraint(["account_id"], ["ledger_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entry_id"], ["ledger_journal_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_id", "line_number", name="uq_journal_lines_entry_line"),
    )
    op.create_index("ix_journal_lines_account_id", "ledger_journal_lines", ["account_id"])

    op.create_table(
        "provider_usage_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_provider_usage_quantity_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_id", "idempotency_key", name="uq_provider_usage_tenant_provider_idem"),
    )
    op.create_index("ix_provider_usage_tenant_provider", "provider_usage_event", ["tenant_id", "provider_id"])

    op.create_table(
        "provider_cost_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("cost_type", sa.String(length=64), nullable=False),
        sa.Column("usage_event_id", sa.String(length=36), nullable=True),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_provider_cost_amount_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_provider_cost_currency"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["ledger_journal_entries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usage_event_id"], ["provider_usage_event.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_id", "idempotency_key", name="uq_provider_cost_tenant_provider_idem"),
    )
    op.create_index("ix_provider_cost_tenant_provider", "provider_cost_event", ["tenant_id", "provider_id"])

    # ---- append-only enforcement at the database layer ----
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_journal_entries_append_only "
        "BEFORE UPDATE OR DELETE ON ledger_journal_entries "
        "FOR EACH ROW EXECUTE FUNCTION revenueos_ledger_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_journal_lines_append_only "
        "BEFORE UPDATE OR DELETE ON ledger_journal_lines "
        "FOR EACH ROW EXECUTE FUNCTION revenueos_ledger_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_accounts_no_delete "
        "BEFORE DELETE ON ledger_accounts "
        "FOR EACH ROW EXECUTE FUNCTION revenueos_ledger_append_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_accounts_no_delete ON ledger_accounts")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_lines_append_only ON ledger_journal_lines")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_append_only ON ledger_journal_entries")
    op.execute(DROP_FUNCTION)
    op.drop_index("ix_provider_cost_tenant_provider", table_name="provider_cost_event")
    op.drop_table("provider_cost_event")
    op.drop_index("ix_provider_usage_tenant_provider", table_name="provider_usage_event")
    op.drop_table("provider_usage_event")
    op.drop_index("ix_journal_lines_account_id", table_name="ledger_journal_lines")
    op.drop_table("ledger_journal_lines")
    op.drop_index("ix_journal_entries_tenant_posted", table_name="ledger_journal_entries")
    op.drop_table("ledger_journal_entries")
    op.drop_index("ix_ledger_accounts_tenant_id", table_name="ledger_accounts")
    op.drop_table("ledger_accounts")
