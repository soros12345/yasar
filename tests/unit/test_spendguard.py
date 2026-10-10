"""SpendGuard stub unit tests (deny-by-default, no fabricated ALLOWED)."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import revenueos_identity.models  # noqa: F401  (tenants table for FK resolution)
from revenueos_shared.db import Base
from revenueos_spendguard.models import (
    SPendGuardState_ALLOWED,
    SPendGuardState_DENIED,
    SPendGuardState_UNVERIFIED,
    SpendGuardDecision,
)
from revenueos_spendguard.service import allow_stub, evaluate_stub

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


def test_evaluate_stub_records_unverified_and_never_allowed(db):
    decision = evaluate_stub(db, tenant_id="t1", correlation_id="c1", intent="post_journal_entry")
    assert isinstance(decision, SpendGuardDecision)
    assert decision.state == SPendGuardState_UNVERIFIED
    assert decision.state != SPendGuardState_ALLOWED
    assert "UNVERIFIED" in decision.reason


def test_explicit_deny_path_records_denied(db):
    decision = evaluate_stub(
        db, tenant_id="t1", correlation_id="c1", intent="post_journal_entry", deny=True
    )
    assert decision.state == SPendGuardState_DENIED
    assert "denied" in decision.reason.lower()


def test_every_evaluation_is_recorded_for_audit(db):
    evaluate_stub(db, tenant_id="t1", correlation_id="c1", intent="post_journal_entry")
    evaluate_stub(db, tenant_id="t1", correlation_id="c1", intent="post_journal_entry", deny=True)
    rows = (
        db.execute(select(SpendGuardDecision).where(SpendGuardDecision.tenant_id == "t1"))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert {r.state for r in rows} == {SPendGuardState_UNVERIFIED, SPendGuardState_DENIED}


def test_allow_stub_is_the_only_path_to_allowed(db):
    decision = evaluate_stub(db, tenant_id="t1", correlation_id="c1", intent="outbox_flush")
    assert decision.state == SPendGuardState_UNVERIFIED
    row = allow_stub(db, decision.id, "t1")
    assert row.state == SPendGuardState_ALLOWED
    assert "test only" in row.reason


def test_allow_stub_is_tenant_scoped_and_unknown_id_rejected(db):
    decision = evaluate_stub(db, tenant_id="t1", correlation_id="c1", intent="outbox_flush")
    with pytest.raises(ValueError, match="not found"):
        allow_stub(db, decision.id, "other-tenant")
    with pytest.raises(ValueError, match="not found"):
        allow_stub(db, "does-not-exist", "t1")
