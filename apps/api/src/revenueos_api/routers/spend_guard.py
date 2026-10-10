"""SpendGuard budget + decision surface (V1A-4).

Budgets are write-restricted to TENANT_ADMIN (wildcard policy); decisions and
budgets are readable by OPERATOR/VIEWER. Deny-by-default is enforced by the
engine, not by these routes.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from revenueos_schemas.execution import (
    SpendBudgetCreateRequest,
    SpendBudgetOut,
)
from revenueos_shared.db import session_scope
from revenueos_spendguard.models import SpendGuardBudget, SpendGuardDecision
from revenueos_spendguard.service import list_budgets, set_budget
from revenueos_ledger.validation import PostingError

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.spend_guard")
router = APIRouter(prefix="/api/v1/spend-guard", tags=["spend-guard"])


def _budget_out(b: SpendGuardBudget) -> SpendBudgetOut:
    return SpendBudgetOut(
        id=b.id,
        tenant_id=b.tenant_id,
        provider_id=b.provider_id,
        currency=b.currency,
        period=b.period,
        limit_amount=str(b.limit_amount),
        enabled=b.enabled,
        note=b.note,
    )


@router.get("/budgets", response_model=list[SpendBudgetOut])
def list_budgets_route(
    principal: Principal = Depends(permission("spend_guard_budget", "read")),
) -> list[SpendBudgetOut]:
    with session_scope() as db:
        return [_budget_out(b) for b in list_budgets(db, principal.tenant_id)]


@router.post("/budgets", response_model=SpendBudgetOut, status_code=201)
def set_budget_route(
    payload: SpendBudgetCreateRequest,
    principal: Principal = Depends(permission("spend_guard_budget", "write")),
) -> SpendBudgetOut:
    with session_scope() as db:
        try:
            row = set_budget(
                db,
                tenant_id=principal.tenant_id,
                currency=payload.currency,
                limit_amount=payload.limit_amount,
                provider_id=payload.provider_id,
                period=payload.period,
                note=payload.note,
            )
        except (ValueError, PostingError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _budget_out(row)


@router.get("/decisions")
def list_decisions_route(
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(permission("spend_guard_decision", "read")),
) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(SpendGuardDecision)
            .where(SpendGuardDecision.tenant_id == principal.tenant_id)
            .order_by(SpendGuardDecision.created_at.desc(), SpendGuardDecision.id)
            .limit(max(1, min(limit, 200)))
            .offset(max(0, offset))
        ).scalars()
        return [
            {
                "id": d.id,
                "tenant_id": d.tenant_id,
                "correlation_id": d.correlation_id,
                "intent": d.intent,
                "state": d.state,
                "reason": d.reason,
                "created_at": d.created_at,
            }
            for d in rows
        ]
