"""V1A-4 execution adapters: capability registry, spend budgets, execution policies,
and approval decisions.

Adds the enforced-guard tables behind the V1A-3 authority chain and the columns
that let an approval request gate (and be linked to) an execution run.

Revision ID: 0006_execution_adapters
Revises: 0005_execution
Create Date: 2026-10-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_execution_adapters"
down_revision: Union[str, None] = "0005_execution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_capabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("verification_state", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capability_id", name="uq_provider_capabilities_capability_id"),
    )
    op.create_index("ix_provider_capabilities_provider", "provider_capabilities", ["provider_id"])
    op.create_index(
        "ix_provider_capabilities_state", "provider_capabilities", ["verification_state", "enabled"]
    )

    op.create_table(
        "spend_guard_budgets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "provider_id", "currency", "period",
            name="uq_spend_budget_tenant_provider_currency_period",
        ),
    )
    op.create_index("ix_spend_budgets_tenant", "spend_guard_budgets", ["tenant_id"])

    op.create_table(
        "execution_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "intent", name="uq_execution_policy_tenant_intent"),
    )
    op.create_index("ix_execution_policies_tenant", "execution_policies", ["tenant_id"])

    op.add_column("approval_requests", sa.Column("run_id", sa.String(length=36), nullable=True))
    op.add_column("approval_requests", sa.Column("decided_by", sa.String(length=36), nullable=True))
    op.add_column(
        "approval_requests", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("approval_requests", sa.Column("decision_note", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_approval_requests_run_id",
        "approval_requests",
        "execution_controller_runs",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_approval_requests_run", "approval_requests", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_requests_run", table_name="approval_requests")
    op.drop_constraint("fk_approval_requests_run_id", "approval_requests", type_="foreignkey")
    op.drop_column("approval_requests", "decision_note")
    op.drop_column("approval_requests", "decided_at")
    op.drop_column("approval_requests", "decided_by")
    op.drop_column("approval_requests", "run_id")

    op.drop_index("ix_execution_policies_tenant", table_name="execution_policies")
    op.drop_table("execution_policies")

    op.drop_index("ix_spend_budgets_tenant", table_name="spend_guard_budgets")
    op.drop_table("spend_guard_budgets")

    op.drop_index("ix_provider_capabilities_state", table_name="provider_capabilities")
    op.drop_index("ix_provider_capabilities_provider", table_name="provider_capabilities")
    op.drop_table("provider_capabilities")
