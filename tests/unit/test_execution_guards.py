"""V1A-4 enforced-guard engine unit tests (real in-memory DB, no network).

Covers: capability registry (deny-by-default), production SpendGuard budget
evaluation, execution policy, advisory-lock fallback, the provider-adapter
framework, and the approval decision engine (terminal-once).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import revenueos_identity.models  # noqa: F401  (tenants table for FK resolution)
import revenueos_ledger.models  # noqa: F401  (provider_cost_event for spend)
from revenueos_capabilities.service import (
    GUARD_ALLOWED,
    GUARD_DENIED,
    capability_guard,
    register_capability,
)
from revenueos_execution_controller.adapters import (
    AdapterDeniedError,
    AdapterError,
    LocalTransport,
    ProviderAdapter,
    get_adapter,
    invoke_adapter,
    register_adapter,
)
from revenueos_execution_controller.approval import (
    ApprovalError,
    create_approval_request,
    decide_approval,
)
from revenueos_execution_controller.policy import evaluate_policy, set_policy
from revenueos_execution_controller.locks import acquire_execution_lock
from revenueos_ledger.models import ProviderCostEvent
from revenueos_shared.db import Base
from revenueos_spendguard.service import evaluate_spend, set_budget

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


# --------------------------------------------------------------------------
# capabilities
# --------------------------------------------------------------------------
def test_unregistered_capability_is_denied(db):
    assert capability_guard(db, "no-such-capability")[0] == GUARD_DENIED


def test_registered_but_unverified_capability_is_denied(db):
    register_capability(
        db, provider_id="awin", capability_id="awin_publisher_redirect", enabled=True
    )
    assert get_adapter("awin_publisher").enabled is False
    state, reason = capability_guard(db, "awin_publisher_redirect")
    assert state == GUARD_DENIED
    assert "UNVERIFIED" in reason


def test_verified_and_enabled_capability_is_allowed(db):
    register_capability(
        db, provider_id="p", capability_id="cap.ok",
        verification_state="VERIFIED", enabled=True,
    )
    assert capability_guard(db, "cap.ok")[0] == GUARD_ALLOWED


def test_disabled_capability_is_denied_even_if_verified(db):
    register_capability(
        db, provider_id="p", capability_id="cap.off",
        verification_state="VERIFIED", enabled=False,
    )
    assert capability_guard(db, "cap.off")[0] == GUARD_DENIED


def test_capability_scope_enforced(db):
    register_capability(
        db, provider_id="p", capability_id="cap.scoped",
        verification_state="VERIFIED", enabled=True,
        scope={"units": ["click"], "max_amount": "5"},
    )
    assert capability_guard(db, "cap.scoped", unit="click", amount="3")[0] == GUARD_ALLOWED
    assert capability_guard(db, "cap.scoped", unit="impression", amount="1")[0] == GUARD_DENIED
    assert capability_guard(db, "cap.scoped", unit="click", amount="6")[0] == GUARD_DENIED


# --------------------------------------------------------------------------
# SpendGuard budgets
# --------------------------------------------------------------------------
def test_no_budget_is_not_applicable_and_recorded(db):
    decision = evaluate_spend(db, tenant_id="t1", correlation_id="c1", intent="outbox_flush")
    assert decision.state == "NOT_APPLICABLE"
    assert decision.state != "ALLOWED"


def test_within_budget_is_allowed_over_budget_denied(db):
    set_budget(db, tenant_id="t1", provider_id="p1", currency="USD", limit_amount="10")
    within = evaluate_spend(
        db, tenant_id="t1", correlation_id="c1", intent="ingest_provider_event",
        provider_id="p1", currency="USD", amount="4",
    )
    assert within.state == "ALLOWED"
    over = evaluate_spend(
        db, tenant_id="t1", correlation_id="c2", intent="ingest_provider_event",
        provider_id="p1", currency="USD", amount="11",
    )
    assert over.state == "DENIED"


def test_recorded_spend_counts_against_budget(db):
    set_budget(db, tenant_id="t1", provider_id="p1", currency="USD", limit_amount="10")
    db.add(
        ProviderCostEvent(
            id=uuid.uuid4().hex, tenant_id="t1", provider_id="p1",
            occurred_at=datetime.now(timezone.utc), amount=Decimal("8"),
            currency="USD", cost_type="api_call",
        )
    )
    db.flush()
    decision = evaluate_spend(
        db, tenant_id="t1", correlation_id="c1", intent="ingest_provider_event",
        provider_id="p1", currency="USD", amount="3",
    )
    assert decision.state == "DENIED"  # 8 recorded + 3 requested > 10


def test_budget_is_tenant_scoped(db):
    set_budget(db, tenant_id="t1", provider_id="p1", currency="USD", limit_amount="10")
    other = evaluate_spend(
        db, tenant_id="t2", correlation_id="c1", intent="ingest_provider_event",
        provider_id="p1", currency="USD", amount="1",
    )
    assert other.state == "NOT_APPLICABLE"


# --------------------------------------------------------------------------
# policy
# --------------------------------------------------------------------------
def test_internal_intent_allowed_by_default(db):
    state, requires_approval, _ = evaluate_policy(db, "t1", "post_journal_entry")
    assert state == GUARD_ALLOWED
    assert requires_approval is False


def test_unknown_intent_denied_by_default(db):
    state, requires_approval, reason = evaluate_policy(db, "t1", "invoke_adapter")
    assert state == GUARD_DENIED
    assert requires_approval is True
    assert "deny-by-default" in reason


def test_explicit_policy_overrides_default(db):
    set_policy(db, tenant_id="t1", intent="invoke_adapter", effect="ALLOW")
    assert evaluate_policy(db, "t1", "invoke_adapter")[0] == GUARD_ALLOWED
    set_policy(db, tenant_id="t1", intent="invoke_adapter", effect="DENY", requires_approval=True)
    state, requires_approval, _ = evaluate_policy(db, "t1", "invoke_adapter")
    assert state == GUARD_DENIED and requires_approval is True


# --------------------------------------------------------------------------
# locks
# --------------------------------------------------------------------------
def test_sqlite_lock_is_not_applicable_not_fabricated(db):
    state, reason = acquire_execution_lock(db, "t1", "outbox_flush")
    assert state == "NOT_APPLICABLE"
    assert "PostgreSQL" in reason


# --------------------------------------------------------------------------
# adapters
# --------------------------------------------------------------------------
class _EchoAdapter(ProviderAdapter):
    adapter_id = "echo"
    capability_id = "cap.echo"
    enabled = True

    def invoke(self, transport, operation, params):
        return transport.send(self.adapter_id, operation, params)


def test_awin_adapter_is_registered_and_disabled():
    awin = get_adapter("awin_publisher")
    assert awin is not None
    assert awin.enabled is False
    assert awin.capability_id == "awin_publisher_redirect"


def test_unknown_adapter_is_rejected(db):
    with pytest.raises(AdapterError, match="unknown adapter"):
        invoke_adapter(db, adapter_id="nope", operation="x")


def test_adapter_denied_before_transport_for_unverified_capability(db):
    from revenueos_execution_controller.adapters import AwinPublisherAdapter

    transport = LocalTransport()
    with pytest.raises(AdapterDeniedError):
        invoke_adapter(
            db, adapter_id="awin_publisher", operation="publisher_redirect",
            transport=transport,
        )
    assert transport.calls == [], "no transport call may happen for a denied capability"


def test_verified_capability_dispatches_through_local_transport(db):
    from revenueos_execution_controller.adapters import _REGISTRY

    register_capability(
        db, provider_id="p", capability_id="cap.echo",
        verification_state="VERIFIED", enabled=True,
    )
    transport = LocalTransport()
    register_adapter(_EchoAdapter())
    try:
        result = invoke_adapter(
            db, adapter_id="echo", operation="ping", params={"a": 1}, transport=transport,
        )
    finally:
        _REGISTRY.pop("echo", None)
    assert result.status == "DISPATCHED"
    assert transport.calls == [{"adapter_id": "echo", "operation": "ping", "params": {"a": 1}}]


# --------------------------------------------------------------------------
# approvals
# --------------------------------------------------------------------------
def test_approval_decision_is_terminal_once(db):
    req = create_approval_request(
        db, tenant_id="t1", requested_by="u1", request_type="spend", correlation_id="c1"
    )
    assert req.status == "PENDING"
    decided = decide_approval(
        db, request_id=req.id, tenant_id="t1", decided_by="u2", decision="APPROVED", note="ok"
    )
    assert decided.status == "APPROVED"
    assert decided.decided_by == "u2"
    assert decided.decided_at is not None
    with pytest.raises(ApprovalError, match="not PENDING"):
        decide_approval(
            db, request_id=req.id, tenant_id="t1", decided_by="u3", decision="DENIED"
        )


def test_denied_approval_is_recorded(db):
    req = create_approval_request(
        db, tenant_id="t1", requested_by="u1", request_type="spend", correlation_id="c1"
    )
    decided = decide_approval(
        db, request_id=req.id, tenant_id="t1", decided_by="u2", decision="DENIED", note="no"
    )
    assert decided.status == "DENIED"
    assert decided.decision_note == "no"
