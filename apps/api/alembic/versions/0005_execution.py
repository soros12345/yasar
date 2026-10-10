"""V1A-3 execution authority: controller runs, events, outbox, approval requests.

Append-only execution_events + outbox_events; execution_controller_runs is the
audit trail of every execution decision; approval_requests is deny-by-default.

Revision ID: 0005_execution
Revises: 0004_ledger_purge_path_fix
Create Date: 2026-10-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_execution"
down_revision: Union[str, None] = "0004_ledger_purge_path_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



# execution_events is an immutable observation log: UPDATE/DELETE are forbidden
# except through the controlled operator escape hatch GUC, mirroring the ledger.
APPEND_ONLY_FUNCTION = """
CREATE OR REPLACE FUNCTION revenueos_execution_events_append_only() RETURNS trigger AS $$
BEGIN
  IF current_setting('revenueos.allow_execution_purge', true) = 'on' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    ELSE
      RETURN NEW;
    END IF;
  END IF;
  RAISE EXCEPTION
    'RevenueOS execution events are append-only: % on % is forbidden', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql
"""

DROP_APPEND_ONLY_FUNCTION = "DROP FUNCTION IF EXISTS revenueos_execution_events_append_only()"

def upgrade() -> None:
    op.create_table(
        "execution_controller_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=True),
        sa.Column("capability_state", sa.String(length=32), nullable=False),
        sa.Column("spend_guard_state", sa.String(length=32), nullable=False),
        sa.Column("policy_state", sa.String(length=32), nullable=False),
        sa.Column("lock_state", sa.String(length=32), nullable=False),
        sa.Column("risk_state", sa.String(length=32), nullable=False),
        sa.Column("approval_state", sa.String(length=32), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exec_runs_tenant_status", "execution_controller_runs", ["tenant_id", "status"])
    op.create_index("ix_exec_runs_correlation", "execution_controller_runs", ["correlation_id"])
    op.create_index("ix_exec_runs_tenant_intent", "execution_controller_runs", ["tenant_id", "intent"])

    op.create_table(
        "execution_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("causation_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_events_tenant_correlation", "execution_events", ["tenant_id", "correlation_id"])
    op.create_index("ix_execution_events_tenant_type", "execution_events", ["tenant_id", "event_type"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("destination", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_tenant_state", "outbox_events", ["tenant_id", "state"])
    op.create_index("ix_outbox_events_correlation", "outbox_events", ["correlation_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("request_type", sa.String(length=64), nullable=False),
        sa.Column("subject_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_tenant_status", "approval_requests", ["tenant_id", "status"])
    op.create_index("ix_approval_requests_correlation", "approval_requests", ["correlation_id"])
    op.create_index("ix_approval_requests_tenant_type", "approval_requests", ["tenant_id", "request_type"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_state", sa.String(length=64), nullable=False),
        sa.Column("verification_outcome", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_verify_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_tenant_status", "workflow_instances", ["tenant_id", "status"])
    op.create_index("ix_workflow_correlation", "workflow_instances", ["correlation_id"])

    op.create_table(
        "spend_guard_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spendguard_tenant_state", "spend_guard_decisions", ["tenant_id", "state"])
    op.create_index("ix_spendguard_correlation", "spend_guard_decisions", ["correlation_id"])

    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_execution_events_append_only "
        "BEFORE UPDATE OR DELETE ON execution_events "
        "FOR EACH ROW EXECUTE FUNCTION revenueos_execution_events_append_only()"
    )


def downgrade() -> None:
    op.drop_index("ix_spendguard_correlation", table_name="spend_guard_decisions")
    op.drop_index("ix_spendguard_tenant_state", table_name="spend_guard_decisions")
    op.drop_table("spend_guard_decisions")

    op.drop_index("ix_workflow_correlation", table_name="workflow_instances")
    op.drop_index("ix_workflow_tenant_status", table_name="workflow_instances")
    op.drop_table("workflow_instances")

    op.drop_index("ix_approval_requests_tenant_type", table_name="approval_requests")
    op.drop_index("ix_approval_requests_correlation", table_name="approval_requests")
    op.drop_index("ix_approval_requests_tenant_status", table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index("ix_outbox_events_correlation", table_name="outbox_events")
    op.drop_index("ix_outbox_events_tenant_state", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.execute("DROP TRIGGER IF EXISTS trg_execution_events_append_only ON execution_events")
    op.drop_index("ix_execution_events_tenant_type", table_name="execution_events")
    op.drop_index("ix_execution_events_tenant_correlation", table_name="execution_events")
    op.drop_table("execution_events")
    op.execute(DROP_APPEND_ONLY_FUNCTION)

    op.drop_index("ix_exec_runs_tenant_intent", table_name="execution_controller_runs")
    op.drop_index("ix_exec_runs_correlation", table_name="execution_controller_runs")
    op.drop_index("ix_exec_runs_tenant_status", table_name="execution_controller_runs")
    op.drop_table("execution_controller_runs")
