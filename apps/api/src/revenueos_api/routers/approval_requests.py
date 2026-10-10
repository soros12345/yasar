"""Approval requests surface (V1A-3). Deny-by-default.

Read: any role with approval_request:read can list their tenant's approval
requests. Create: record-only stub (TENANT_ADMIN-only via wildcard policy).
Approve/deny: not implemented in V1A-3 — protected routes returning 501, so
there is no unauthenticated path to influence an approval.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from revenueos_execution_controller.models import ApprovalRequest
from revenueos_schemas.execution import ApprovalRequestOut
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.approval_requests")
router = APIRouter(prefix="/api/v1/approval-requests", tags=["approval-requests"])


def _approval_out(a: ApprovalRequest) -> ApprovalRequestOut:
    return ApprovalRequestOut(
        id=a.id,
        tenant_id=a.tenant_id,
        correlation_id=a.correlation_id,
        request_type=a.request_type,
        subject_json=a.subject_json,
        status=a.status,
        requested_by=a.requested_by,
        expires_at=a.expires_at,
        created_at=a.created_at,
    )


@router.get("", response_model=list[ApprovalRequestOut])
def list_approval_requests_route(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(permission("approval_request", "read")),
) -> list[ApprovalRequestOut]:
    with session_scope() as db:
        rows = db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.tenant_id == principal.tenant_id)
            .order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id)
            .limit(limit)
            .offset(offset)
        ).scalars()
        return [_approval_out(a) for a in rows]


@router.post("", response_model=ApprovalRequestOut, status_code=201)
def create_approval_request_route(
    request_type: str = Query(min_length=1, max_length=64),
    correlation_id: str = Query(min_length=1, max_length=36),
    principal: Principal = Depends(permission("approval_request", "write")),
) -> ApprovalRequestOut:
    """Record-only stub. Real approval creation/decisions are deferred (V1A-4)."""
    with session_scope() as db:
        req = ApprovalRequest(
            id=uuid.uuid4().hex,
            tenant_id=principal.tenant_id,
            correlation_id=correlation_id,
            request_type=request_type,
            subject_json=None,
            status="PENDING",
            requested_by=principal.user_id,
        )
        db.add(req)
        db.flush()
        return _approval_out(req)


@router.post("/{request_id}/approve", status_code=501)
def approve_route(
    request_id: str,
    principal: Principal = Depends(permission("approval_request", "write")),
) -> dict:
    """Not implemented in V1A-3 — the approval workflow is deferred."""
    raise HTTPException(status_code=501, detail="approval workflow not implemented in V1A-3")


@router.post("/{request_id}/deny", status_code=501)
def deny_route(
    request_id: str,
    principal: Principal = Depends(permission("approval_request", "write")),
) -> dict:
    """Not implemented in V1A-3 — the approval workflow is deferred."""
    raise HTTPException(status_code=501, detail="approval workflow not implemented in V1A-3")
