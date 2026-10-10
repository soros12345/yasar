"""Workflow state service: query-verify-retry with explicit terminal states."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_workflow_state.models import (
    VERIFICATION_OUTCOME_FAILED,
    VERIFICATION_OUTCOME_UNVERIFIED,
    VERIFICATION_OUTCOME_VERIFIED,
    WORKFLOW_STATUS_AWAITING_VERIFICATION,
    WORKFLOW_STATUS_CANCELLED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_PENDING,
    WORKFLOW_STATUS_RUNNING,
    WORKFLOW_STATUS_SUCCEEDED,
    WorkflowInstance,
)


TERMINAL_STATES = (
    WORKFLOW_STATUS_SUCCEEDED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_CANCELLED,
)


class WorkflowError(Exception):
    pass


class WorkflowAlreadyTerminal(WorkflowError):
    pass


def start_workflow(
    db: DbSession,
    *,
    tenant_id: str,
    correlation_id: str,
    workflow_type: str,
) -> WorkflowInstance:
    if not tenant_id or not correlation_id or not workflow_type:
        raise WorkflowError("tenant_id, correlation_id and workflow_type are required")
    existing = db.execute(
        select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == tenant_id,
            WorkflowInstance.correlation_id == correlation_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    inst = WorkflowInstance(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        workflow_type=workflow_type,
        status=WORKFLOW_STATUS_PENDING,
        current_state="start",
    )
    db.add(inst)
    db.flush()
    return inst


def advance_to_running(db: DbSession, workflow_id: str, tenant_id: str) -> WorkflowInstance:
    row = db.execute(
        select(WorkflowInstance).where(
            WorkflowInstance.id == workflow_id, WorkflowInstance.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise WorkflowError("workflow instance not found")
    if row.status in TERMINAL_STATES:
        raise WorkflowAlreadyTerminal(f"workflow already terminal: {row.status}")
    row.status = WORKFLOW_STATUS_RUNNING
    row.current_state = "running"
    db.flush()
    return row


def mark_awaiting_verification(db: DbSession, workflow_id: str, tenant_id: str) -> WorkflowInstance:
    row = _get_row(db, workflow_id, tenant_id)
    if row.status in TERMINAL_STATES:
        raise WorkflowAlreadyTerminal(f"workflow already terminal: {row.status}")
    row.status = WORKFLOW_STATUS_AWAITING_VERIFICATION
    row.current_state = "awaiting_verification"
    db.flush()
    return row


def record_verification(
    db: DbSession,
    workflow_id: str,
    tenant_id: str,
    *,
    outcome: str,
    detail: str | None = None,
) -> WorkflowInstance:
    """Record a verification outcome. Terminal only on VERIFIED or VERIFICATION_FAILED.

    A workflow is terminal exactly once: recording any further outcome on a
    terminal instance is rejected (no implicit retry after a verdict)."""
    row = _get_row(db, workflow_id, tenant_id)
    if row.status in TERMINAL_STATES:
        raise WorkflowAlreadyTerminal(f"workflow already terminal: {row.status}")
    if outcome == VERIFICATION_OUTCOME_VERIFIED:
        row.verification_outcome = VERIFICATION_OUTCOME_VERIFIED
        row.status = WORKFLOW_STATUS_SUCCEEDED
        row.current_state = "verified"
    elif outcome == VERIFICATION_OUTCOME_FAILED:
        row.verification_outcome = VERIFICATION_OUTCOME_FAILED
        row.status = WORKFLOW_STATUS_FAILED
        row.current_state = "verification_failed"
        if detail:
            row.error_detail = detail
    else:
        raise WorkflowError(f"unknown verification outcome: {outcome!r}")
    row.last_verify_at = datetime.now(timezone.utc)
    db.flush()
    return row


def record_failure(db: DbSession, workflow_id: str, tenant_id: str, detail: str) -> WorkflowInstance:
    row = _get_row(db, workflow_id, tenant_id)
    if row.status in TERMINAL_STATES:
        raise WorkflowAlreadyTerminal(f"workflow already terminal: {row.status}")
    row.status = WORKFLOW_STATUS_FAILED
    row.current_state = "failed"
    row.error_detail = detail
    db.flush()
    return row


def record_cancel(db: DbSession, workflow_id: str, tenant_id: str) -> WorkflowInstance:
    row = _get_row(db, workflow_id, tenant_id)
    if row.status in TERMINAL_STATES:
        raise WorkflowAlreadyTerminal(f"workflow already terminal: {row.status}")
    row.status = WORKFLOW_STATUS_CANCELLED
    row.current_state = "cancelled"
    db.flush()
    return row


def list_workflows(
    db: DbSession,
    tenant_id: str,
    *,
    workflow_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkflowInstance]:
    q = (
        select(WorkflowInstance)
        .where(WorkflowInstance.tenant_id == tenant_id)
        .order_by(WorkflowInstance.created_at.desc(), WorkflowInstance.id)
    )
    if workflow_type:
        q = q.where(WorkflowInstance.workflow_type == workflow_type)
    if status:
        q = q.where(WorkflowInstance.status == status)
    q = q.limit(max(1, min(limit, 200))).offset(max(0, offset))
    return list(db.execute(q).scalars())


def _get_row(db: DbSession, workflow_id: str, tenant_id: str) -> WorkflowInstance:
    row = db.execute(
        select(WorkflowInstance).where(
            WorkflowInstance.id == workflow_id, WorkflowInstance.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise WorkflowError("workflow instance not found in tenant")
    return row
