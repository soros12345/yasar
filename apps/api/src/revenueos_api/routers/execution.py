"""Execution authority endpoints (V1A-3).

Deny-by-default. Every intent passes:
  Casbin -> ExecutionController (Decision/Plan/Capability/SpendGuard/Policy/
  Locks/Risk/Approval -> Execution -> Verification).

Correlation IDs are mandatory and the plan payload is persisted on the run, so
execution is deterministic and replayable by correlation id. Every stub guard
state is returned explicitly as UNVERIFIED — no authorization is fabricated.

Read models: execution_controller_run, execution_event, outbox_event,
workflow_instance. Writes stay TENANT_ADMIN-only via the wildcard policy.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_execution_controller.models import ExecutionControllerRun
from revenueos_execution_controller.service import (
    SUPPORTED_INTENTS,
    ExecutionError,
    execute_intent,
    list_runs,
    plan_execution,
    verify_execution,
)
from revenueos_event_backbone.service import list_events, list_pending_outbox
from revenueos_schemas.execution import (
    ExecutionEventOut,
    ExecutionPlanRequest,
    ExecutionRunOut,
    OutboxEventOut,
    WorkflowInstanceOut,
)
from revenueos_workflow_state.models import WorkflowInstance
from revenueos_workflow_state.service import (
    WorkflowError,
    list_workflows,
    mark_awaiting_verification,
    start_workflow,
)
from revenueos_shared.db import session_scope

from revenueos_api.deps import Principal, permission

logger = logging.getLogger("revenueos.api.execution")
router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


def _run_out(run: ExecutionControllerRun) -> ExecutionRunOut:
    return ExecutionRunOut(
        id=run.id,
        tenant_id=run.tenant_id,
        correlation_id=run.correlation_id,
        intent=run.intent,
        status=run.status,
        decision_json=run.decision_json,
        capability_state=run.capability_state,
        spend_guard_state=run.spend_guard_state,
        policy_state=run.policy_state,
        lock_state=run.lock_state,
        risk_state=run.risk_state,
        approval_state=run.approval_state,
        error_detail=run.error_detail,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _workflow_out(w: WorkflowInstance) -> WorkflowInstanceOut:
    return WorkflowInstanceOut(
        id=w.id,
        tenant_id=w.tenant_id,
        correlation_id=w.correlation_id,
        workflow_type=w.workflow_type,
        status=w.status,
        current_state=w.current_state,
        verification_outcome=w.verification_outcome,
        attempt_count=w.attempt_count,
        last_verify_at=w.last_verify_at,
        error_detail=w.error_detail,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


@router.post("/decide", response_model=ExecutionRunOut, status_code=201)
def decide_route(
    payload: ExecutionPlanRequest,
    principal: Principal = Depends(permission("execution_controller_run", "write")),
) -> ExecutionRunOut:
    """Stage 1-8: record the decision + plan and every guard stub state."""
    if payload.intent not in SUPPORTED_INTENTS:
        raise HTTPException(status_code=400, detail=f"unknown intent: {payload.intent}")
    with session_scope() as db:
        run = plan_execution(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            intent=payload.intent,
            payload=payload.payload,
            correlation_id=payload.correlation_id,
        )
        return _run_out(run)


@router.post("/runs/{run_id}/execute", response_model=ExecutionRunOut)
def execute_route(
    run_id: str,
    principal: Principal = Depends(permission("execution_controller_run", "write")),
) -> ExecutionRunOut:
    """Stage 9: execute a PLANNED run through the controller. Executes once."""
    with session_scope() as db:
        run = _get_run(db, run_id, principal.tenant_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run_not_found")
        try:
            execute_intent(db, run)
        except ExecutionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception as exc:  # execution failed: run is recorded FAILED
            logger.warning(
                "execution failed",
                extra={
                    "event": "execution_failed",
                    "component": "execution",
                    "detail": f"run_id={run_id} error={type(exc).__name__}",
                },
            )
            raise HTTPException(status_code=400, detail=f"execution_failed: {type(exc).__name__}")
        return _run_out(run)


@router.post("/runs/{run_id}/verify", response_model=ExecutionRunOut)
def verify_run_route(
    run_id: str,
    outcome: str = Query(min_length=1, max_length=32),
    principal: Principal = Depends(permission("execution_controller_run", "write")),
) -> ExecutionRunOut:
    """Stage 10: record the verification outcome (query-verify-retry boundary)."""
    with session_scope() as db:
        run = _get_run(db, run_id, principal.tenant_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run_not_found")
        verify_execution(db, run.id, principal.tenant_id, run.correlation_id, outcome)
        return _run_out(run)


@router.get("/runs", response_model=list[ExecutionRunOut])
def list_runs_route(
    status: str | None = None,
    intent: str | None = None,
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(permission("execution_controller_run", "read")),
) -> list[ExecutionRunOut]:
    with session_scope() as db:
        runs = list_runs(
            db, principal.tenant_id, status=status, intent=intent, limit=limit, offset=offset
        )
        return [_run_out(r) for r in runs]


@router.get("/runs/{run_id}", response_model=ExecutionRunOut)
def get_run_route(
    run_id: str,
    principal: Principal = Depends(permission("execution_controller_run", "read")),
) -> ExecutionRunOut:
    with session_scope() as db:
        run = _get_run(db, run_id, principal.tenant_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run_not_found")
        return _run_out(run)


@router.get("/events", response_model=list[ExecutionEventOut])
def list_events_route(
    correlation_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(permission("execution_event", "read")),
) -> list[ExecutionEventOut]:
    with session_scope() as db:
        events = list_events(
            db,
            principal.tenant_id,
            correlation_id=correlation_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
        return [
            ExecutionEventOut(
                id=e.id,
                tenant_id=e.tenant_id,
                correlation_id=e.correlation_id,
                causation_id=e.causation_id,
                event_type=e.event_type,
                payload_json=e.payload_json,
                occurred_at=e.occurred_at,
            )
            for e in events
        ]


@router.get("/outbox/pending", response_model=list[OutboxEventOut])
def list_pending_outbox_route(
    principal: Principal = Depends(permission("outbox_event", "read")),
) -> list[OutboxEventOut]:
    with session_scope() as db:
        pending = list_pending_outbox(db, principal.tenant_id, limit=100)
        return [
            OutboxEventOut(
                id=o.id,
                tenant_id=o.tenant_id,
                correlation_id=o.correlation_id,
                destination=o.destination,
                payload_json=o.payload_json,
                state=o.state,
                attempts=o.attempts,
                created_at=o.created_at,
                dispatched_at=o.dispatched_at,
            )
            for o in pending
        ]


@router.post("/workflows", response_model=WorkflowInstanceOut, status_code=201)
def start_workflow_route(
    workflow_type: str = Query(min_length=1, max_length=64),
    correlation_id: str = Query(min_length=1, max_length=36),
    principal: Principal = Depends(permission("workflow_instance", "write")),
) -> WorkflowInstanceOut:
    with session_scope() as db:
        inst = start_workflow(
            db,
            tenant_id=principal.tenant_id,
            correlation_id=correlation_id,
            workflow_type=workflow_type,
        )
        return _workflow_out(inst)


@router.get("/workflows", response_model=list[WorkflowInstanceOut])
def list_workflows_route(
    workflow_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(permission("workflow_instance", "read")),
) -> list[WorkflowInstanceOut]:
    with session_scope() as db:
        rows = list_workflows(
            db,
            principal.tenant_id,
            workflow_type=workflow_type,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [_workflow_out(w) for w in rows]


@router.post("/workflows/{workflow_id}/verify", response_model=WorkflowInstanceOut)
def verify_workflow_route(
    workflow_id: str,
    outcome: str = Query(min_length=1, max_length=32),
    detail: str | None = None,
    principal: Principal = Depends(permission("workflow_instance", "write")),
) -> WorkflowInstanceOut:
    from revenueos_workflow_state.service import record_verification

    with session_scope() as db:
        try:
            mark_awaiting_verification(db, workflow_id, principal.tenant_id)
            inst = record_verification(
                db, workflow_id, principal.tenant_id, outcome=outcome, detail=detail
            )
        except WorkflowError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return _workflow_out(inst)


def _get_run(db: DbSession, run_id: str, tenant_id: str) -> ExecutionControllerRun | None:
    return db.execute(
        select(ExecutionControllerRun).where(
            ExecutionControllerRun.id == run_id,
            ExecutionControllerRun.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
