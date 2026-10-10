"""Unit tests for the ExecutionController state machine (real in-memory DB).

Covers: decision/plan recording (exactly one audit run), guard stub states,
deny/reject paths, outbox idempotency + dispatch, and the query-verify-retry
boundary. Ledger-backed execution is covered by the integration suite.
"""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import revenueos_identity.models  # noqa: F401  (registers tenants for FK resolution)
from revenueos_execution_controller.models import RUN_STATUS_PLANNED, RUN_STATUS_SUCCEEDED, ExecutionControllerRun
from revenueos_execution_controller.service import (
    EXECUTION_INTENT_OUTBOX_FLUSH,
    ExecutionError,
    ExecutionPlan,
    decide,
    execute_intent,
    execute_post_entry,
    plan,
    plan_execution,
)
from revenueos_event_backbone.models import ExecutionEvent
from revenueos_event_backbone.service import enqueue_outbox, list_pending_outbox, mark_outbox_dispatched
from revenueos_shared.db import Base
from revenueos_spendguard.models import SPendGuardState_UNVERIFIED, SpendGuardDecision

pytestmark = pytest.mark.unit


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def _events(db, correlation_id):
    return (
        db.execute(select(ExecutionEvent).where(ExecutionEvent.correlation_id == correlation_id))
        .scalars()
        .all()
    )


def test_decide_records_exactly_one_run_and_one_event(db):
    p = decide(db, tenant_id="t1", user_id="u1", intent="post_journal_entry", payload={"lines": []})
    assert p.correlation_id
    assert p.intent == "post_journal_entry"
    assert p.spend_guard_state == "UNVERIFIED"
    runs = db.execute(select(ExecutionControllerRun)).scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "DECIDING"
    events = _events(db, p.correlation_id)
    assert [e.event_type for e in events] == ["execution.decision"]


def test_plan_requires_intent_and_correlation(db):
    p = ExecutionPlan(intent="post_journal_entry", correlation_id="c1", tenant_id="t1", user_id="u1", payload={})
    assert plan(db, p) is p
    with pytest.raises(ValueError, match="execution plan must declare an intent"):
        plan(db, ExecutionPlan(intent="", correlation_id="c1", tenant_id="t1", user_id="u1", payload={}))
    with pytest.raises(ValueError, match="execution plan must declare a correlation_id"):
        plan(db, ExecutionPlan(intent="post_journal_entry", correlation_id="", tenant_id="t1", user_id="u1", payload={}))


def test_plan_execution_records_planned_run_with_payload_and_enforced_guards(db):
    payload = {"tenant_scoped": True}
    run = plan_execution(
        db, tenant_id="t1", user_id="u1", intent="outbox_flush", payload=payload, correlation_id="corr-plan-1"
    )
    assert run.status == RUN_STATUS_PLANNED
    assert run.correlation_id == "corr-plan-1"
    assert run.decision_json["payload"] == payload
    assert run.decision_json["user_id"] == "u1"
    # V1A-4 enforced guards: an internal intent is policy-ALLOWED; guards with no
    # configured authority are NOT_APPLICABLE, never a fabricated ALLOWED.
    assert run.capability_state == "NOT_APPLICABLE"
    assert run.policy_state == "ALLOWED"
    assert run.spend_guard_state == "NOT_APPLICABLE"
    assert run.lock_state == "NOT_APPLICABLE"  # SQLite has no advisory locks
    assert run.risk_state == "NOT_APPLICABLE"
    assert run.approval_state == "NOT_APPLICABLE"
    assert len(db.execute(select(ExecutionControllerRun)).scalars().all()) == 1
    assert [e.event_type for e in _events(db, "corr-plan-1")] == ["execution.plan"]
    # SpendGuard recorded why it was NOT_APPLICABLE (no budget configured)
    decisions = db.execute(select(SpendGuardDecision)).scalars().all()
    assert len(decisions) == 1
    assert decisions[0].state == "NOT_APPLICABLE"


def test_execute_intent_rejects_unknown_and_non_planned_runs(db):
    run = plan_execution(
        db, tenant_id="t1", user_id="u1", intent="outbox_flush", payload={}, correlation_id="corr-x"
    )
    run.intent = "delete_everything"
    with pytest.raises(ExecutionError, match="unknown intent"):
        execute_intent(db, run)

    run2 = plan_execution(
        db, tenant_id="t1", user_id="u1", intent="outbox_flush", payload={}, correlation_id="corr-y"
    )
    execute_intent(db, run2)
    assert run2.status == RUN_STATUS_SUCCEEDED
    with pytest.raises(ExecutionError, match="only PLANNED runs are executable"):
        execute_intent(db, run2)


def test_outbox_enqueue_is_idempotent_and_dispatch_is_recorded(db):
    first = enqueue_outbox(db, tenant_id="t1", correlation_id="c1", destination="valkey", payload={"a": 1})
    second = enqueue_outbox(db, tenant_id="t1", correlation_id="c1", destination="valkey", payload={"a": 2})
    assert first.id == second.id
    other = enqueue_outbox(db, tenant_id="t1", correlation_id="c1", destination="postgres", payload=None)
    assert other.id != first.id

    pending = list_pending_outbox(db, "t1")
    assert len(pending) == 2
    mark_outbox_dispatched(db, first.id, "t1")
    assert first.state == "dispatched"
    assert first.dispatched_at is not None  # regression: tz-aware timestamp
    assert len(list_pending_outbox(db, "t1")) == 1
    # a second dispatch is a no-op (idempotent), not an error
    again = mark_outbox_dispatched(db, first.id, "t1")
    assert again.state == "dispatched"
    with pytest.raises(ValueError, match="not found in tenant"):
        mark_outbox_dispatched(db, first.id, "other-tenant")


def test_outbox_flush_execution_dispatches_pending_for_its_own_tenant(db):
    mine = enqueue_outbox(db, tenant_id="t1", correlation_id="c1", destination="valkey", payload=None)
    theirs = enqueue_outbox(db, tenant_id="t2", correlation_id="c1", destination="valkey", payload=None)
    run = plan_execution(
        db, tenant_id="t1", user_id="u1", intent=EXECUTION_INTENT_OUTBOX_FLUSH, payload={}, correlation_id="c-flush"
    )
    result = execute_intent(db, run)
    assert run.status == RUN_STATUS_SUCCEEDED
    assert result.outbox_id == mine.id
    db.refresh(mine)
    db.refresh(theirs)
    assert mine.state == "dispatched"
    assert theirs.state == "pending", "outbox flush must never cross tenants"
    assert "execution.outbox_dispatched" in [e.event_type for e in _events(db, "c-flush")]


def test_execute_post_entry_rejects_unsupported_intent(db):
    p = ExecutionPlan(
        intent="delete_journal_entry",
        correlation_id="c1",
        tenant_id="t1",
        user_id="u1",
        payload={"lines": [], "currency": "USD", "description": "x", "idempotency_key": "k"},
    )
    with pytest.raises(ValueError, match="does not support intent"):
        execute_post_entry(db, p)
