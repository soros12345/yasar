"""Approval requests surface (V1A-4).

Deny-by-default and terminal-once. Read requires approval_request:read; create
and decisions require approval_request:write (TENANT_ADMIN via wildcard policy).
An approved request linked to an execution run releases that run to PLANNED; a
denied request parks the run as DENIED.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from revenueos_execution_controller.approval import (
    ApprovalError,
    create_approval_request,
    decide_approval,
    get_approval_request,
)
from revenueos_execution_controller.models import ApprovalRequest
from revenueos_schemas.execution import ApprovalDecisionRequest, ApprovalRequestOut
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
    run_id: str | None = Query(default=None, max_length=36),
    principal: Principal = Depends(permission("approval_request", "write")),
) -> ApprovalRequestOut:
    with session_scope() as db:
        req = create_approval_request(
            db,
            tenant_id=principal.tenant_id,
            requested_by=principal.user_id,
            request_type=request_type,
            correlation_id=correlation_id,
            run_id=run_id,
        )
        return _approval_out(req)


def _decide(
    request_id: str,
    decision: str,
    note: str | None,
    principal: Principal,
) -> ApprovalRequestOut:
    with session_scope() as db:
        existing = get_approval_request(db, request_id, principal.tenant_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="approval_request_not_found")
        try:
            req = decide_approval(
                db,
                request_id=request_id,
                tenant_id=principal.tenant_id,
                decided_by=principal.user_id,
                decision=decision,
                note=note,
            )
        except ApprovalError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return _approval_out(req)


@router.post("/{request_id}/approve", response_model=ApprovalRequestOut)
def approve_route(
    request_id: str,
    payload: ApprovalDecisionRequest | None = None,
    principal: Principal = Depends(permission("approval_request", "write")),
) -> ApprovalRequestOut:
    note = payload.note if payload else None
    return _decide(request_id, "APPROVED", note, principal)


@router.post("/{request_id}/deny", response_model=ApprovalRequestOut)
def deny_route(
    request_id: str,
    payload: ApprovalDecisionRequest | None = None,
    principal: Principal = Depends(permission("approval_request", "write")),
) -> ApprovalRequestOut:
    note = payload.note if payload else None
    return _decide(request_id, "DENIED", note, principal)
