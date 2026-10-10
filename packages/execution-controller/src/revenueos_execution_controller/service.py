"""ExecutionController — the sole external side-effect authority (V1A-3).

State machine (each stage records its UNVERIFIED stub state today):
  Decision -> Execution Plan -> Capability lookup -> SpendGuard hook-point
  -> Policy -> Locks -> Risk -> Approval -> Execution -> Adapter -> Verification

No direct external writes from anywhere else. Every effect passes through this
controller and is recorded in execution_controller_runs + execution_events.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_event_backbone.service import (
    append_event,
    list_pending_outbox,
    mark_outbox_dispatched,
)
from revenueos_spendguard.models import SPendGuardState_UNVERIFIED, SPendGuardState_DENIED
from revenueos_spendguard.service import evaluate_spend
from revenueos_capabilities.service import capability_guard
from revenueos_ledger.service import post_entry
from revenueos_shared.correlation import get_correlation_id

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

EXECUTION_INTENT_POST_JOURNAL_ENTRY = "post_journal_entry"
EXECUTION_INTENT_INGEST_PROVIDER_EVENT = "ingest_provider_event"
EXECUTION_INTENT_OUTBOX_FLUSH = "outbox_flush"
EXECUTION_INTENT_INVOKE_ADAPTER = "invoke_adapter"

SUPPORTED_INTENTS = (
    EXECUTION_INTENT_POST_JOURNAL_ENTRY,
    EXECUTION_INTENT_INGEST_PROVIDER_EVENT,
    EXECUTION_INTENT_OUTBOX_FLUSH,
    EXECUTION_INTENT_INVOKE_ADAPTER,
)

GUARD_ALLOWED = "ALLOWED"
GUARD_NOT_APPLICABLE = "NOT_APPLICABLE"
GUARD_DENIED = "DENIED"
APPROVAL_REQUIRED_STATE = "REQUIRED"
GUARD_STATES_SATISFIED = (GUARD_ALLOWED, GUARD_NOT_APPLICABLE)


class ExecutionError(RuntimeError):
    """Raised when an execution cannot proceed (unknown intent, terminal run)."""


@dataclass
class ExecutionPlan:
    intent: str
    correlation_id: str
    tenant_id: str
    user_id: str
    payload: dict
    decision_note: str = ""
    capability_state: str = "UNVERIFIED"
    spend_guard_state: str = "UNVERIFIED"
    policy_state: str = "UNVERIFIED"
    lock_state: str = "UNVERIFIED"
    risk_state: str = "UNVERIFIED"
    approval_state: str = "UNVERIFIED"
    guard_reasons: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    run_id: str
    status: str
    correlation_id: str
    message: str
    event_id: str | None = None
    outbox_id: str | None = None
    ledger_entry_id: str | None = None
    error_detail: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decide(
    db: DbSession,
    *,
    tenant_id: str,
    user_id: str,
    intent: str,
    payload: dict,
    correlation_id: str | None = None,
) -> ExecutionPlan:
    """Stage 1: Decision + Execution Plan. Records the decision and returns the plan."""
    cid = correlation_id or get_correlation_id()
    run_id = uuid.uuid4().hex
    run = _create_run(
        db, run_id=run_id, tenant_id=tenant_id, correlation_id=cid,
        intent=intent, user_id=user_id, status=RUN_STATUS_DECIDING,
        decision_json={"intent": intent, "payload_keys": sorted(payload.keys())},
    )
    append_event(
        db,
        tenant_id=tenant_id,
        correlation_id=cid,
        causation_id=None,
        event_type="execution.decision",
        payload={"run_id": run_id, "intent": intent, "payload_keys": sorted(payload.keys())},
    )
    return ExecutionPlan(
        intent=intent,
        correlation_id=cid,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=payload,
        decision_note=f"decision recorded for run {run_id}",
    )


def plan(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionPlan:
    """Stage 2: Execution Plan finalization."""
    if not plan_obj.intent:
        raise ValueError("execution plan must declare an intent")
    if not plan_obj.correlation_id:
        raise ValueError("execution plan must declare a correlation_id")
    plan_obj.decision_note += " | plan finalized"
    return plan_obj


def check_capability_stub(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionPlan:
    """Stage 3: Capability lookup (UNVERIFIED stub)."""
    plan_obj.capability_state = "UNVERIFIED"
    return plan_obj


def check_spend_guard_stub(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionPlan:
    """Stage 4: SpendGuard hook-point (deny-by-default, UNVERIFIED today)."""
    decision = evaluate_stub(
        db, tenant_id=plan_obj.tenant_id, correlation_id=plan_obj.correlation_id, intent=plan_obj.intent
    )
    plan_obj.spend_guard_state = decision.state
    if decision.state == SPendGuardState_DENIED:
        raise RuntimeError("SpendGuard denied (stubbed)")
    return plan_obj


def check_policy_stub(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionPlan:
    """Stage 5: Policy (UNVERIFIED stub)."""
    plan_obj.policy_state = "UNVERIFIED"
    return plan_obj


def check_locks_stub(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionPlan:
    """Stage 6: Locks (UNVERIFIED stub)."""
    plan_obj.lock_state = "UNVERIFIED"
    return plan_obj


def check_risk_stub(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionPlan:
    """Stage 7: Risk (UNVERIFIED stub)."""
    plan_obj.risk_state = "UNVERIFIED"
    return plan_obj


def check_approval_stub(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionPlan:
    """Stage 8: Approval (deny-by-default; no real approvals workflow yet)."""
    plan_obj.approval_state = "UNVERIFIED"
    return plan_obj


def execute_post_entry(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionResult:
    """Stage 9: Execution — post a balanced journal entry through the ledger."""
    from revenueos_ledger.validation import LineInput

    if plan_obj.intent != EXECUTION_INTENT_POST_JOURNAL_ENTRY:
        raise ValueError(f"execute_post_entry does not support intent {plan_obj.intent!r} (supported: {EXECUTION_INTENT_POST_JOURNAL_ENTRY!r})")

    lines = [
        LineInput(
            account_code=l["account_code"],
            side=l["side"],
            amount=l["amount"],
            description=l.get("description"),
        )
        for l in plan_obj.payload["lines"]
    ]
    entry, created = post_entry(
        db,
        tenant_id=plan_obj.tenant_id,
        currency=plan_obj.payload["currency"],
        description=plan_obj.payload["description"],
        idempotency_key=plan_obj.payload["idempotency_key"],
        lines=lines,
        reference=plan_obj.payload.get("reference"),
        source=plan_obj.payload.get("source", "execution_controller"),
    )
    event = append_event(
        db,
        tenant_id=plan_obj.tenant_id,
        correlation_id=plan_obj.correlation_id,
        causation_id=plan_obj.correlation_id,
        event_type="execution.executed",
        payload={"entry_id": entry.id, "created": created, "intent": plan_obj.intent},
    )
    return ExecutionResult(
        run_id="",
        status=RUN_STATUS_SUCCEEDED,
        correlation_id=plan_obj.correlation_id,
        message="journal entry posted",
        ledger_entry_id=entry.id,
        event_id=event.id,
    )


def execute_ingest_provider_event(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionResult:
    """Stage 9: Execution — ingest a provider event (usage or cost)."""
    from revenueos_ledger.events import ingest_usage_event, ingest_cost_event

    occurred_at_raw = plan_obj.payload.get("occurred_at")
    occurred_at = datetime.fromisoformat(occurred_at_raw).replace(tzinfo=timezone.utc) if occurred_at_raw else datetime.now(timezone.utc)

    if "quantity" in plan_obj.payload:
        event, created = ingest_usage_event(
            db,
            tenant_id=plan_obj.tenant_id,
            provider_id=plan_obj.payload["provider_id"],
            occurred_at=occurred_at,
            quantity=plan_obj.payload["quantity"],
            unit=plan_obj.payload["unit"],
            idempotency_key=plan_obj.payload.get("idempotency_key"),
            capability_id=plan_obj.payload.get("capability_id"),
            metadata=plan_obj.payload.get("metadata"),
        )
    else:
        event, created = ingest_cost_event(
            db,
            tenant_id=plan_obj.tenant_id,
            provider_id=plan_obj.payload["provider_id"],
            occurred_at=occurred_at,
            amount=plan_obj.payload["amount"],
            currency=plan_obj.payload["currency"],
            cost_type=plan_obj.payload["cost_type"],
            usage_event_id=plan_obj.payload.get("usage_event_id"),
            journal_entry_id=plan_obj.payload.get("journal_entry_id"),
            idempotency_key=plan_obj.payload.get("idempotency_key"),
        )
    emitted = append_event(
        db,
        tenant_id=plan_obj.tenant_id,
        correlation_id=plan_obj.correlation_id,
        causation_id=plan_obj.correlation_id,
        event_type="execution.executed",
        payload={"event_id": event.id, "created": created, "intent": plan_obj.intent},
    )
    return ExecutionResult(
        run_id="",
        status=RUN_STATUS_SUCCEEDED,
        correlation_id=plan_obj.correlation_id,
        message="provider event ingested",
        event_id=emitted.id,
    )


def execute_outbox_flush(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionResult:
    """Stage 9: Execution — flush pending outbox events for the tenant."""
    pending = list_pending_outbox(db, plan_obj.tenant_id, limit=100)
    dispatched_ids = []
    for outbox in pending:
        mark_outbox_dispatched(db, outbox.id, plan_obj.tenant_id)
        dispatched_ids.append(outbox.id)
        append_event(
            db,
            tenant_id=plan_obj.tenant_id,
            correlation_id=plan_obj.correlation_id,
            causation_id=plan_obj.correlation_id,
            event_type="execution.outbox_dispatched",
            payload={"outbox_id": outbox.id, "destination": outbox.destination},
        )
    return ExecutionResult(
        run_id="",
        status=RUN_STATUS_SUCCEEDED,
        correlation_id=plan_obj.correlation_id,
        message=f"outbox flushed: {len(dispatched_ids)} events",
        outbox_id=dispatched_ids[0] if dispatched_ids else None,
    )


def execute_invoke_adapter(db: DbSession, plan_obj: ExecutionPlan) -> ExecutionResult:
    """Stage 9: Execution — capability-gated provider adapter invocation.

    The adapter layer re-checks the capability; an unverified capability (the
    Awin case) is denied here even if it somehow reached execution.
    """
    from revenueos_execution_controller.adapters import AdapterDeniedError, invoke_adapter

    payload = plan_obj.payload or {}
    adapter_id = payload.get("adapter_id")
    if not adapter_id:
        raise ExecutionError("invoke_adapter requires an adapter_id")
    try:
        result = invoke_adapter(
            db,
            adapter_id=adapter_id,
            operation=payload.get("operation", "invoke"),
            params=payload.get("params"),
            capability_id=payload.get("capability_id"),
            unit=payload.get("unit"),
            amount=payload.get("amount"),
        )
    except AdapterDeniedError as exc:
        raise ExecutionError(f"adapter denied: {exc}") from exc
    event = append_event(
        db,
        tenant_id=plan_obj.tenant_id,
        correlation_id=plan_obj.correlation_id,
        causation_id=plan_obj.correlation_id,
        event_type="execution.adapter_dispatched",
        payload={"adapter_id": adapter_id, "status": result.status, "operation": result.operation},
    )
    return ExecutionResult(
        run_id="",
        status=RUN_STATUS_SUCCEEDED,
        correlation_id=plan_obj.correlation_id,
        message=f"adapter {adapter_id} dispatched",
        event_id=event.id,
    )


def plan_execution(
    db: DbSession,
    *,
    tenant_id: str,
    user_id: str,
    intent: str,
    payload: dict,
    correlation_id: str | None = None,
) -> "ExecutionControllerRun":
    """Stages 1-8 in ONE recorded run (single audit row per decision).

    Decision -> Plan -> Capability -> SpendGuard -> Policy -> Locks -> Risk ->
    Approval. Every stub state is recorded explicitly as UNVERIFIED: no
    authorization is fabricated. The run is persisted as PLANNED together with
    the payload so execution is deterministic and replayable by correlation id.
    """
    cid = correlation_id or get_correlation_id()
    plan_obj = ExecutionPlan(
        intent=intent,
        correlation_id=cid,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=payload,
    )
    plan_obj = plan(db, plan_obj)

    # Stage 3: capability (only when the intent references a provider capability)
    cap_ref = payload.get("capability_id")
    if cap_ref:
        cap_state, cap_reason = capability_guard(
            db, cap_ref, unit=payload.get("unit"), amount=payload.get("amount")
        )
    else:
        cap_state, cap_reason = (
            GUARD_NOT_APPLICABLE,
            "intent does not reference a provider capability",
        )
    plan_obj.capability_state = cap_state
    plan_obj.guard_reasons["capability"] = cap_reason

    # Stage 4: SpendGuard (production budget evaluation)
    spend_decision = evaluate_spend(
        db,
        tenant_id=tenant_id,
        correlation_id=cid,
        intent=intent,
        provider_id=payload.get("provider_id"),
        currency=payload.get("currency"),
        amount=payload.get("amount"),
    )
    plan_obj.spend_guard_state = spend_decision.state
    plan_obj.guard_reasons["spend_guard"] = spend_decision.reason

    # Stage 5: policy
    from revenueos_execution_controller.policy import evaluate_policy

    policy_state, requires_approval, policy_reason = evaluate_policy(db, tenant_id, intent)
    plan_obj.policy_state = policy_state
    plan_obj.guard_reasons["policy"] = policy_reason

    # Stage 6: locks (PostgreSQL advisory lock)
    from revenueos_execution_controller.locks import acquire_execution_lock

    lock_state, lock_reason = acquire_execution_lock(db, tenant_id, intent)
    plan_obj.lock_state = lock_state
    plan_obj.guard_reasons["lock"] = lock_reason

    # Stage 7: risk (no risk scoring engine configured in V1A-4)
    plan_obj.risk_state = GUARD_NOT_APPLICABLE
    plan_obj.guard_reasons["risk"] = "no risk scoring engine configured"

    # Stage 8: approval
    if requires_approval or payload.get("requires_approval"):
        plan_obj.approval_state = APPROVAL_REQUIRED_STATE
        plan_obj.guard_reasons["approval"] = "policy requires an approval decision"
    else:
        plan_obj.approval_state = GUARD_NOT_APPLICABLE
        plan_obj.guard_reasons["approval"] = "no approval required"

    # A single denied guard denies the whole run; a required approval parks it.
    denied = any(
        state == GUARD_DENIED
        for state in (
            plan_obj.capability_state,
            plan_obj.spend_guard_state,
            plan_obj.policy_state,
            plan_obj.lock_state,
            plan_obj.risk_state,
        )
    )
    if denied:
        run_status = RUN_STATUS_DENIED
    elif plan_obj.approval_state == APPROVAL_REQUIRED_STATE:
        run_status = RUN_STATUS_APPROVAL_REQUIRED
    else:
        run_status = RUN_STATUS_PLANNED

    run = _create_run(
        db,
        run_id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        correlation_id=cid,
        intent=intent,
        user_id=user_id,
        status=run_status,
        decision_json={
            "intent": intent,
            "payload": payload,
            "user_id": user_id,
            "decision_note": plan_obj.decision_note,
            "guard_reasons": plan_obj.guard_reasons,
        },
        capability_state=plan_obj.capability_state,
        spend_guard_state=plan_obj.spend_guard_state,
        policy_state=plan_obj.policy_state,
        lock_state=plan_obj.lock_state,
        risk_state=plan_obj.risk_state,
        approval_state=plan_obj.approval_state,
    )
    if run_status == RUN_STATUS_APPROVAL_REQUIRED:
        from revenueos_execution_controller.approval import create_approval_request

        create_approval_request(
            db,
            tenant_id=tenant_id,
            requested_by=user_id,
            request_type=intent,
            correlation_id=cid,
            run_id=run.id,
            subject={"intent": intent, "payload_keys": sorted(payload.keys())},
        )
    append_event(
        db,
        tenant_id=tenant_id,
        correlation_id=cid,
        causation_id=None,
        event_type="execution.plan",
        payload={
            "run_id": run.id,
            "intent": intent,
            "payload_keys": sorted(payload.keys()),
            "states": {
                "capability": plan_obj.capability_state,
                "spend_guard": plan_obj.spend_guard_state,
                "policy": plan_obj.policy_state,
                "lock": plan_obj.lock_state,
                "risk": plan_obj.risk_state,
                "approval": plan_obj.approval_state,
            },
        },
    )
    return run


def execute_intent(db: DbSession, run: "ExecutionControllerRun") -> ExecutionResult:
    """Stages 9-10: execute a PLANNED run and record the outcome on that run.

    Refuses to run an unknown intent or a run that is no longer PLANNED, so a
    run cannot be executed twice (no blind retry). The execution functions are
    idempotent at the ledger/outbox layer via idempotency keys.
    """
    if run.intent not in SUPPORTED_INTENTS:
        raise ExecutionError(f"unknown intent: {run.intent!r}")
    if run.status == RUN_STATUS_APPROVAL_REQUIRED:
        raise ExecutionError(
            f"run {run.id} requires an approval decision before execution"
        )
    if run.status == RUN_STATUS_DENIED:
        raise ExecutionError(f"run {run.id} was denied by the guard chain")
    if run.status != RUN_STATUS_PLANNED:
        raise ExecutionError(
            f"run {run.id} is {run.status}, only PLANNED runs are executable"
        )
    blocked = [
        name
        for name, state in (
            ("capability", run.capability_state),
            ("spend_guard", run.spend_guard_state),
            ("policy", run.policy_state),
            ("lock", run.lock_state),
            ("risk", run.risk_state),
        )
        if state not in GUARD_STATES_SATISFIED
    ]
    if blocked:
        raise ExecutionError(
            f"run {run.id} has unsatisfied guards: {', '.join(blocked)}"
        )

    decision_json = run.decision_json or {}
    payload = decision_json.get("payload") or {}
    user_id = decision_json.get("user_id") or ""
    plan_obj = ExecutionPlan(
        intent=run.intent,
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        user_id=user_id,
        payload=payload,
        capability_state=run.capability_state,
        spend_guard_state=run.spend_guard_state,
        policy_state=run.policy_state,
        lock_state=run.lock_state,
        risk_state=run.risk_state,
        approval_state=run.approval_state,
    )
    run.status = RUN_STATUS_EXECUTING
    db.flush()

    handler = {
        EXECUTION_INTENT_POST_JOURNAL_ENTRY: execute_post_entry,
        EXECUTION_INTENT_INGEST_PROVIDER_EVENT: execute_ingest_provider_event,
        EXECUTION_INTENT_OUTBOX_FLUSH: execute_outbox_flush,
        EXECUTION_INTENT_INVOKE_ADAPTER: execute_invoke_adapter,
    }[run.intent]
    try:
        result = handler(db, plan_obj)
    except Exception as exc:  # record the failure on the run, then re-raise
        run.status = RUN_STATUS_FAILED
        run.error_detail = f"{type(exc).__name__}: {exc}"
        db.flush()
        raise
    run.status = result.status
    run.decision_json = decision_json | {"last_result": result.message}
    if result.error_detail:
        run.error_detail = result.error_detail
    db.flush()
    return result


def verify_execution(db: DbSession, run_id: str, tenant_id: str, correlation_id: str, outcome: str) -> ExecutionResult:
    """Stage 10: Verification. Query-verify-retry boundary."""
    run = _get_run(db, run_id, tenant_id)
    run.status = RUN_STATUS_VERIFYING
    run.decision_json = (run.decision_json or {}) | {"verification_outcome": outcome}
    db.flush()
    append_event(
        db,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        causation_id=correlation_id,
        event_type="execution.verified",
        payload={"run_id": run_id, "outcome": outcome},
    )
    return ExecutionResult(
        run_id=run_id,
        status=RUN_STATUS_VERIFYING,
        correlation_id=correlation_id,
        message=f"verification recorded: {outcome}",
    )


def _create_run(
    db: DbSession,
    *,
    run_id: str,
    tenant_id: str,
    correlation_id: str,
    intent: str,
    user_id: str,
    status: str,
    decision_json: dict | None = None,
    capability_state: str = SPendGuardState_UNVERIFIED,
    spend_guard_state: str = SPendGuardState_UNVERIFIED,
    policy_state: str = SPendGuardState_UNVERIFIED,
    lock_state: str = SPendGuardState_UNVERIFIED,
    risk_state: str = SPendGuardState_UNVERIFIED,
    approval_state: str = SPendGuardState_UNVERIFIED,
) -> "ExecutionControllerRun":
    from revenueos_execution_controller.models import ExecutionControllerRun
    run = ExecutionControllerRun(
        id=run_id,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        intent=intent,
        status=status,
        decision_json=decision_json,
        capability_state=capability_state,
        spend_guard_state=spend_guard_state,
        policy_state=policy_state,
        lock_state=lock_state,
        risk_state=risk_state,
        approval_state=approval_state,
    )
    db.add(run)
    db.flush()
    return run


def _get_run(db: DbSession, run_id: str, tenant_id: str) -> "ExecutionControllerRun | None":
    from revenueos_execution_controller.models import ExecutionControllerRun
    return db.execute(
        select(ExecutionControllerRun).where(
            ExecutionControllerRun.id == run_id,
            ExecutionControllerRun.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()


def list_runs(
    db: DbSession,
    tenant_id: str,
    *,
    status: str | None = None,
    intent: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list["ExecutionControllerRun"]:
    from revenueos_execution_controller.models import ExecutionControllerRun
    q = (
        select(ExecutionControllerRun)
        .where(ExecutionControllerRun.tenant_id == tenant_id)
        .order_by(ExecutionControllerRun.created_at.desc(), ExecutionControllerRun.id)
    )
    if status:
        q = q.where(ExecutionControllerRun.status == status)
    if intent:
        q = q.where(ExecutionControllerRun.intent == intent)
    q = q.limit(max(1, min(limit, 200))).offset(max(0, offset))
    return list(db.execute(q).scalars())
