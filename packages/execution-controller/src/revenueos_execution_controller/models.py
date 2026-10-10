"""Execution controller run + approval request models (V1A-3).

execution_controller_runs is the audit trail of every execution decision that
passed through the controller. approval_requests is the deny-by-default
approval surface (no real approvals workflow yet).
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from revenueos_shared.db import Base

RUN_STATUS_PENDING = "PENDING"
RUN_STATUS_DECIDING = "DECIDING"
RUN_STATUS_PLANNED = "PLANNED"
RUN_STATUS_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
RUN_STATUS_APPROVED = "APPROVED"
RUN_STATUS_DENIED = "DENIED"
RUN_STATUS_EXECUTING = "EXECUTING"
RUN_STATUS_SUCCEEDED = "SUCCEEDED"
RUN_STATUS_FAILED = "FAILED"
RUN_STATUS_VERIFYING = "VERIFYING"
RUN_STATUS_TERMINAL_STATES = (
    RUN_STATUS_SUCCEEDED,
    RUN_STATUS_FAILED,
    RUN_STATUS_DENIED,
)

APPROVAL_STATUS_PENDING = "PENDING"
APPROVAL_STATUS_APPROVED = "APPROVED"
APPROVAL_STATUS_DENIED = "DENIED"
APPROVAL_STATUS_EXPIRED = "EXPIRED"


class ExecutionControllerRun(Base):
    __tablename__ = "execution_controller_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RUN_STATUS_PENDING)
    decision_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    capability_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    spend_guard_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    policy_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    lock_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    risk_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    approval_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_exec_runs_tenant_status", "tenant_id", "status"),
        Index("ix_exec_runs_correlation", "correlation_id"),
        Index("ix_exec_runs_tenant_intent", "tenant_id", "intent"),
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=APPROVAL_STATUS_PENDING
    )
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    # V1A-4: link an approval to the execution run it gates, and record the decision.
    run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("execution_controller_runs.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_approval_requests_tenant_status", "tenant_id", "status"),
        Index("ix_approval_requests_correlation", "correlation_id"),
        Index("ix_approval_requests_tenant_type", "tenant_id", "request_type"),
        Index("ix_approval_requests_run", "run_id"),
    )


# register the policy table on Base.metadata with this package
from revenueos_execution_controller import policy as _policy  # noqa: E402,F401
