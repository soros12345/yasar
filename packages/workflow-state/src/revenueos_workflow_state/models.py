"""Workflow state models (V1A-3).

A workflow instance is a long-lived uncertain-result procedure. It is terminal
exactly once. Retry is explicit: query-verify-retry, never blind retry.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from revenueos_shared.db import Base

WORKFLOW_STATUS_PENDING = "PENDING"
WORKFLOW_STATUS_RUNNING = "RUNNING"
WORKFLOW_STATUS_AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
WORKFLOW_STATUS_SUCCEEDED = "SUCCEEDED"
WORKFLOW_STATUS_FAILED = "FAILED"
WORKFLOW_STATUS_CANCELLED = "CANCELLED"

VERIFICATION_OUTCOME_UNVERIFIED = "UNVERIFIED"
VERIFICATION_OUTCOME_VERIFIED = "VERIFIED"
VERIFICATION_OUTCOME_FAILED = "VERIFICATION_FAILED"


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WORKFLOW_STATUS_PENDING)
    current_state: Mapped[str] = mapped_column(String(64), nullable=False, default="start")
    verification_outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VERIFICATION_OUTCOME_UNVERIFIED
    )
    attempt_count: Mapped[int] = mapped_column(server_default="0", nullable=False)
    last_verify_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_workflow_tenant_status", "tenant_id", "status"),
        Index("ix_workflow_correlation", "correlation_id"),
    )
