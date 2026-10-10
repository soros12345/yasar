"""Execution policy surface (V1A-4).

Policies are write-restricted to TENANT_ADMIN (wildcard policy) and readable by
OPERATOR/VIEWER. Absent an explicit policy, only internal intents are allowed;
everything else is deny-by-default.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from revenueos_execution_controller.policy import ExecutionPolicy, list_policies, set_policy
from revenueos_schemas.execution import ExecutionPolicyCreateRequest, ExecutionPolicyOut
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.execution_policies")
router = APIRouter(prefix="/api/v1/execution-policies", tags=["execution-policies"])


def _out(p: ExecutionPolicy) -> ExecutionPolicyOut:
    return ExecutionPolicyOut(
        id=p.id,
        tenant_id=p.tenant_id,
        intent=p.intent,
        effect=p.effect,
        requires_approval=p.requires_approval,
        enabled=p.enabled,
        note=p.note,
    )


@router.get("", response_model=list[ExecutionPolicyOut])
def list_policies_route(
    principal: Principal = Depends(permission("execution_policy", "read")),
) -> list[ExecutionPolicyOut]:
    with session_scope() as db:
        return [_out(p) for p in list_policies(db, principal.tenant_id)]


@router.post("", response_model=ExecutionPolicyOut, status_code=201)
def set_policy_route(
    payload: ExecutionPolicyCreateRequest,
    principal: Principal = Depends(permission("execution_policy", "write")),
) -> ExecutionPolicyOut:
    with session_scope() as db:
        try:
            row = set_policy(
                db,
                tenant_id=principal.tenant_id,
                intent=payload.intent,
                effect=payload.effect,
                requires_approval=payload.requires_approval,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _out(row)
