"""Workflow state unit tests (query-verify-retry semantics, no DB required)."""
import pytest

from revenueos_workflow_state.models import (
    WORKFLOW_STATUS_AWAITING_VERIFICATION,
    WORKFLOW_STATUS_CANCELLED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_PENDING,
    WORKFLOW_STATUS_RUNNING,
    WORKFLOW_STATUS_SUCCEEDED,
    VERIFICATION_OUTCOME_FAILED,
    VERIFICATION_OUTCOME_UNVERIFIED,
    VERIFICATION_OUTCOME_VERIFIED,
    WorkflowInstance,
)
from revenueos_workflow_state.service import (
    WorkflowAlreadyTerminal,
    mark_awaiting_verification,
    record_cancel,
    record_failure,
    record_verification,
    start_workflow,
)

pytestmark = pytest.mark.unit


def _db():
    # Lightweight in-memory SQLAlchemy session for workflow-state unit tests.
    # Keeps the query-verify-retry boundary contract realistic without a real DB.
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from revenueos_workflow_state.models import WorkflowInstance

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # workflow_instances FKs to tenants; create the minimal shared base for FK resolution.
    from revenueos_shared.db import Base
    from revenueos_identity.models import Tenant  # noqa: F401  (registers tenants table for FK resolution)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()

    def _execute(stmt):
        return session.execute(stmt)

    def _add(obj):
        type(session).add(session, obj)

    def _flush():
        type(session).flush(session)

    def _commit():
        type(session).commit(session)

    def _rollback():
        type(session).rollback(session)

    def _close():
        type(session).close(session)

    def _make():
        return session_factory()

    # Bind the actual SQLAlchemy session methods, avoiding recursion via the
    # monkeypatched `execute` attribute.
    session.add = _add
    session.flush = _flush
    session.commit = _commit
    session.rollback = _rollback
    session.close = _close
    session._make = _make
    return session


def _inst(**overrides):
    base = dict(
        id="wf-1",
        tenant_id="t1",
        correlation_id="corr-1",
        workflow_type="query-verify-retry",
        status=WORKFLOW_STATUS_PENDING,
        current_state="start",
        verification_outcome=VERIFICATION_OUTCOME_UNVERIFIED,
        attempt_count=0,
    )
    base.update(overrides)
    return WorkflowInstance(**base)


def test_start_workflow():
    db = _db()
    inst = start_workflow(db, tenant_id="t1", correlation_id="corr-1", workflow_type="qvr")
    assert isinstance(inst, WorkflowInstance)
    assert inst.status == WORKFLOW_STATUS_PENDING
    assert inst.current_state == "start"


def test_terminal_transitions_are_rejected():
    db = _db()
    inst = start_workflow(db, tenant_id="t1", correlation_id="corr-1", workflow_type="qvr")
    record_verification(db, inst.id, "t1", outcome="VERIFIED")
    with pytest.raises(WorkflowAlreadyTerminal):
        record_cancel(db, inst.id, "t1")
    with pytest.raises(WorkflowAlreadyTerminal):
        record_failure(db, inst.id, "t1", "no retry")


def test_query_verify_retry_flow_is_terminal_exactly_once():
    db = _db()
    inst = start_workflow(db, tenant_id="t1", correlation_id="corr-1", workflow_type="qvr")
    inst = mark_awaiting_verification(db, inst.id, "t1")
    assert inst.status == WORKFLOW_STATUS_AWAITING_VERIFICATION
    inst = record_verification(db, inst.id, "t1", outcome="VERIFIED")
    assert inst.status == WORKFLOW_STATUS_SUCCEEDED
    assert inst.verification_outcome == VERIFICATION_OUTCOME_VERIFIED
    assert inst.last_verify_at is not None
    # Terminal exactly once: no further verdict and no re-verification.
    with pytest.raises(WorkflowAlreadyTerminal):
        record_verification(db, inst.id, "t1", outcome=VERIFICATION_OUTCOME_FAILED)
    with pytest.raises(WorkflowAlreadyTerminal):
        mark_awaiting_verification(db, inst.id, "t1")


def test_failed_verification_is_the_explicit_terminal_branch():
    db = _db()
    inst = start_workflow(db, tenant_id="t1", correlation_id="corr-2", workflow_type="qvr")
    inst = mark_awaiting_verification(db, inst.id, "t1")
    inst = record_verification(
        db, inst.id, "t1", outcome=VERIFICATION_OUTCOME_FAILED, detail="provider not settled"
    )
    assert inst.status == WORKFLOW_STATUS_FAILED
    assert inst.verification_outcome == VERIFICATION_OUTCOME_FAILED
    assert inst.error_detail == "provider not settled"
    with pytest.raises(WorkflowAlreadyTerminal):
        record_verification(db, inst.id, "t1", outcome=VERIFICATION_OUTCOME_VERIFIED)


def test_unknown_verification_outcome_rejected():
    from revenueos_workflow_state.service import WorkflowError

    db = _db()
    inst = start_workflow(db, tenant_id="t1", correlation_id="corr-3", workflow_type="qvr")
    inst = mark_awaiting_verification(db, inst.id, "t1")
    with pytest.raises(WorkflowError, match="unknown verification outcome"):
        record_verification(db, inst.id, "t1", outcome="MAYBE")


def test_verification_is_tenant_scoped():
    from revenueos_workflow_state.service import WorkflowError

    db = _db()
    inst = start_workflow(db, tenant_id="t1", correlation_id="corr-4", workflow_type="qvr")
    with pytest.raises(WorkflowError, match="not found"):
        record_verification(db, inst.id, "other-tenant", outcome=VERIFICATION_OUTCOME_VERIFIED)
