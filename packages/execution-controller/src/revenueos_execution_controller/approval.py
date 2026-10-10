"""Approval decision engine (V1A-4).

An approval request is deny-by-default and terminal once decided. Approving a
request that gates an execution run moves that run from APPROVAL_REQUIRED back
to PLANNED so it becomes executable; denying it moves the run to DENIED.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_event_backbone.service import append_event
from revenueos_execution_controller.models import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_DENIED,
    APPROVAL_STATUS_PENDING,
    RUN_STATUS_APPROVAL_REQUIRED,
    RUN_STATUS_DENIED,
    RUN_STATUS_PLANNED,
    ApprovalRequest,
    ExecutionControllerRun,
)

DECISION_APPROVE = "APPROVED"
DECISION_DENY = "DENIED"


class ApprovalError(RuntimeError):
    """Raised on an invalid approval transition (already decided, unknown)."""


def create_approval_request(
    db: DbSession,
    *,
    tenant_id: str,
    requested_by: str,
    request_type: str,
    correlation_id: str,
    run_id: str | None = None,
    subject: dict | None = None,
) -> ApprovalRequest:
    req = ApprovalRequest(
        id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        request_type=request_type,
        subject_json=subject,
        status=APPROVAL_STATUS_PENDING,
        requested_by=requested_by,
        run_id=run_id,
    )
    db.add(req)
    db.flush()
    append_event(
        db,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        causation_id=correlation_id,
        event_type="approval.requested",
        payload={"request_id": req.id, "request_type": request_type, "run_id": run_id},
    )
    return req


def get_approval_request(
    db: DbSession, request_id: str, tenant_id: str
) -> ApprovalRequest | None:
    return db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.id == request_id, ApprovalRequest.tenant_id == tenant_id
        )
    ).scalar_one_or_none()


def decide_approval(
    db: DbSession,
    *,
    request_id: str,
    tenant_id: str,
    decided_by: str,
    decision: str,
    note: str | None = None,
) -> ApprovalRequest:
    """Approve or deny a pending request. Terminal exactly once."""
    decision = decision.upper().strip()
    if decision not in (DECISION_APPROVE, DECISION_DENY):
        raise ApprovalError(f"invalid decision: {decision!r}")
    req = get_approval_request(db, request_id, tenant_id)
    if req is None:
        raise ApprovalError("approval request not found")
    if req.status != APPROVAL_STATUS_PENDING:
        raise ApprovalError(f"approval request is {req.status}, not PENDING")

    req.status = APPROVAL_STATUS_APPROVED if decision == DECISION_APPROVE else APPROVAL_STATUS_DENIED
    req.decided_by = decided_by
    req.decided_at = datetime.now(timezone.utc)
    req.decision_note = note
    db.flush()

    if req.run_id:
        run = db.execute(
            select(ExecutionControllerRun).where(
                ExecutionControllerRun.id == req.run_id,
                ExecutionControllerRun.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if run is not None:
            if decision == DECISION_APPROVE:
                run.approval_state = "APPROVED"
                if run.status == RUN_STATUS_APPROVAL_REQUIRED:
                    run.status = RUN_STATUS_PLANNED
            else:
                run.approval_state = "DENIED"
                run.status = RUN_STATUS_DENIED
            db.flush()

    append_event(
        db,
        tenant_id=tenant_id,
        correlation_id=req.correlation_id,
        causation_id=req.correlation_id,
        event_type="approval.decided",
        payload={"request_id": req.id, "decision": req.status, "run_id": req.run_id},
    )
    return req
