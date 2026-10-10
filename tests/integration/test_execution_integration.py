"""V1A-3 execution authority integration tests.

Covers: decision/plan recording, ledger execution through the controller,
execute-once semantics, append-only event log, correlation/causation,
outbox pending + flush, approval deny-by-default, RBAC and tenant isolation,
and query-verify-retry. Requires the full native stack (API, PostgreSQL, Valkey).
"""
import uuid

import pytest
from sqlalchemy import delete, select, text

httpx = pytest.importorskip("httpx")

from revenueos_authorization.enforcer import bind_role, ensure_default_policies
from revenueos_execution_controller.models import ApprovalRequest, ExecutionControllerRun
from revenueos_event_backbone.models import ExecutionEvent, OutboxEvent
from revenueos_event_backbone.service import enqueue_outbox
from revenueos_identity.models import (
    ROLE_OPERATOR,
    ROLE_TENANT_ADMIN,
    ROLE_VIEWER,
    Tenant,
    User,
    UserSession,
)
from revenueos_identity.services import create_tenant, create_user
from revenueos_ledger.models import LedgerAccount, LedgerJournalEntry, LedgerJournalLine
from revenueos_ledger.service import create_account
from revenueos_shared.db import get_session_factory, session_scope

BASE = "http://127.0.0.1:8000"
TIMEOUT = 30.0
PASSWORD = "ExecutionTestPass!7"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def world():
    """Two isolated tenants (admin/operator/viewer in A, admin in B)."""
    suffix = uuid.uuid4().hex[:8]
    slug_a, slug_b = f"exa-{suffix}", f"exb-{suffix}"
    with session_scope() as db:
        t_a = create_tenant(db, slug_a, "Execution Tenant A")
        t_b = create_tenant(db, slug_b, "Execution Tenant B")
        a_admin = create_user(db, t_a.id, f"admin@{slug_a}.test", "A Admin", PASSWORD, ROLE_TENANT_ADMIN)
        a_op = create_user(db, t_a.id, f"op@{slug_a}.test", "A Op", PASSWORD, ROLE_OPERATOR)
        a_viewer = create_user(db, t_a.id, f"viewer@{slug_a}.test", "A Viewer", PASSWORD, ROLE_VIEWER)
        b_admin = create_user(db, t_b.id, f"admin@{slug_b}.test", "B Admin", PASSWORD, ROLE_TENANT_ADMIN)
        # ledger accounts for the controller-driven posting
        create_account(db, tenant_id=t_a.id, code="CASH", name="Cash", kind="ASSET", currency="USD")
        create_account(db, tenant_id=t_a.id, code="REVENUE", name="Revenue", kind="REVENUE", currency="USD")
        data = {
            "t_a": t_a.id, "t_b": t_b.id, "slug_a": slug_a, "slug_b": slug_b,
            "a_admin": a_admin.id, "a_op": a_op.id, "a_viewer": a_viewer.id,
            "b_admin": b_admin.id, "suffix": suffix,
        }
    for tid in (data["t_a"], data["t_b"]):
        ensure_default_policies(tid)
    bind_role(data["a_admin"], ROLE_TENANT_ADMIN, data["t_a"])
    bind_role(data["a_op"], ROLE_OPERATOR, data["t_a"])
    bind_role(data["a_viewer"], ROLE_VIEWER, data["t_a"])
    bind_role(data["b_admin"], ROLE_TENANT_ADMIN, data["t_b"])
    yield data

    tenants = [data["t_a"], data["t_b"]]
    with session_scope() as db:
        db.execute(text("SET LOCAL revenueos.allow_execution_purge = 'on'"))
        db.execute(delete(ExecutionEvent).where(ExecutionEvent.tenant_id.in_(tenants)))
        db.execute(delete(OutboxEvent).where(OutboxEvent.tenant_id.in_(tenants)))
        db.execute(delete(ExecutionControllerRun).where(ExecutionControllerRun.tenant_id.in_(tenants)))
        db.execute(delete(ApprovalRequest).where(ApprovalRequest.tenant_id.in_(tenants)))
        db.execute(text("DELETE FROM workflow_instances WHERE tenant_id = ANY(:t)"), {"t": tenants})
        db.execute(text("DELETE FROM spend_guard_decisions WHERE tenant_id = ANY(:t)"), {"t": tenants})
        db.execute(text("DELETE FROM spend_guard_budgets WHERE tenant_id = ANY(:t)"), {"t": tenants})
        db.execute(text("DELETE FROM execution_policies WHERE tenant_id = ANY(:t)"), {"t": tenants})
        db.execute(text("DELETE FROM provider_capabilities WHERE capability_id LIKE 'itest-%'"))
        db.execute(text("SET LOCAL revenueos.allow_ledger_purge = 'on'"))
        db.execute(text(
            "DELETE FROM ledger_journal_lines WHERE entry_id IN "
            "(SELECT id FROM ledger_journal_entries WHERE tenant_id = ANY(:t))"
        ), {"t": tenants})
        db.execute(delete(LedgerJournalEntry).where(LedgerJournalEntry.tenant_id.in_(tenants)))
        db.execute(delete(LedgerAccount).where(LedgerAccount.tenant_id.in_(tenants)))
        db.execute(delete(UserSession).where(UserSession.tenant_id.in_(tenants)))
        db.execute(delete(User).where(User.tenant_id.in_(tenants)))
        db.execute(delete(Tenant).where(Tenant.id.in_(tenants)))

    from revenueos_authorization.models import CasbinRule

    s = get_session_factory()()
    ids = [data[k] for k in ("t_a", "t_b", "a_admin", "a_op", "a_viewer", "b_admin")]
    s.execute(delete(CasbinRule).where(
        CasbinRule.v0.in_(ids) | CasbinRule.v1.in_(ids) | CasbinRule.v2.in_(ids)
    ))
    s.commit()
    s.close()


def token(world, slug_key, email_key):
    r = httpx.post(
        f"{BASE}/api/v1/auth/login",
        json={"tenant_slug": world[slug_key], "email": f"{email_key}@{world[slug_key]}.test", "password": PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def new_cid(tag: str) -> str:
    """Correlation ids are VARCHAR(36) at rest — keep every id within that."""
    return (tag[:5] + uuid.uuid4().hex)[:36]


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def post_entry_payload(key: str) -> dict:
    return {
        "lines": [
            {"account_code": "CASH", "side": "DEBIT", "amount": "25.00"},
            {"account_code": "REVENUE", "side": "CREDIT", "amount": "25.00"},
        ],
        "currency": "USD",
        "description": "controller-driven posting",
        "idempotency_key": key,
    }


def decide(client_token, intent, payload, correlation_id):
    return httpx.post(
        f"{BASE}/api/v1/execution/decide",
        headers=auth(client_token),
        json={"intent": intent, "correlation_id": correlation_id, "payload": payload},
        timeout=TIMEOUT,
    )


# --------------------------------------------------------------------------
# deny-by-default
# --------------------------------------------------------------------------
def test_execution_routes_reject_missing_token(world):
    probes = [
        ("POST", "/api/v1/execution/decide", {"intent": "outbox_flush", "correlation_id": "c", "payload": {}}),
        ("POST", "/api/v1/execution/runs/some-id/execute", None),
        ("POST", "/api/v1/execution/runs/some-id/verify", None),
        ("GET", "/api/v1/execution/runs", None),
        ("GET", "/api/v1/execution/runs/some-id", None),
        ("GET", "/api/v1/execution/events", None),
        ("GET", "/api/v1/execution/outbox/pending", None),
        ("POST", "/api/v1/execution/workflows", None),
        ("GET", "/api/v1/execution/workflows", None),
        ("POST", "/api/v1/execution/workflows/some-id/verify", None),
        ("GET", "/api/v1/approval-requests", None),
        ("POST", "/api/v1/approval-requests", None),
        ("POST", "/api/v1/approval-requests/some-id/approve", None),
        ("POST", "/api/v1/approval-requests/some-id/deny", None),
    ]
    for method, path, body in probes:
        r = httpx.request(method, f"{BASE}{path}", json=body, timeout=TIMEOUT)
        assert r.status_code == 401, f"{method} {path} accepted without token ({r.status_code})"


def test_read_only_roles_cannot_write_execution(world):
    viewer = token(world, "slug_a", "viewer")
    op = token(world, "slug_a", "op")
    cid = new_cid("rbac")
    for tok in (viewer, op):
        r = decide(tok, "outbox_flush", {}, cid)
        assert r.status_code == 403, r.text
        r = httpx.post(
            f"{BASE}/api/v1/approval-requests",
            headers=auth(tok),
            params={"request_type": "spend", "correlation_id": cid},
            timeout=TIMEOUT,
        )
        assert r.status_code == 403, r.text


# --------------------------------------------------------------------------
# decision/plan + ledger execution through the controller
# --------------------------------------------------------------------------
def test_decide_records_planned_run_with_enforced_guard_states(world):
    """V1A-4: an internal intent is policy-ALLOWED; guards with no configured
    authority are NOT_APPLICABLE, never a fabricated ALLOWED. The PostgreSQL
    advisory lock is real, so the lock guard is ALLOWED."""
    admin = token(world, "slug_a", "admin")
    cid = new_cid("decide")
    r = decide(admin, "post_journal_entry", post_entry_payload(f"idem-{cid}"), cid)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PLANNED"
    assert body["correlation_id"] == cid
    assert body["intent"] == "post_journal_entry"
    assert body["capability_state"] == "NOT_APPLICABLE"
    assert body["policy_state"] == "ALLOWED"
    assert body["spend_guard_state"] == "NOT_APPLICABLE"
    assert body["lock_state"] == "ALLOWED"
    assert body["risk_state"] == "NOT_APPLICABLE"
    assert body["approval_state"] == "NOT_APPLICABLE"
    run_id = body["id"]

    r = httpx.get(f"{BASE}/api/v1/execution/runs/{run_id}", headers=auth(admin), timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["status"] == "PLANNED"


def test_execute_post_journal_entry_through_controller(world):
    admin = token(world, "slug_a", "admin")
    cid = new_cid("exec")
    decide_r = decide(admin, "post_journal_entry", post_entry_payload(f"idem-{cid}"), cid)
    assert decide_r.status_code == 201, decide_r.text
    run_id = decide_r.json()["id"]

    r = httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin), timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SUCCEEDED"

    # the posting is real: the tenant's ledger has the entry
    with session_scope() as db:
        entry = db.execute(
            select(LedgerJournalEntry).where(
                LedgerJournalEntry.tenant_id == world["t_a"],
                LedgerJournalEntry.idempotency_key == f"idem-{cid}",
            )
        ).scalar_one_or_none()
        assert entry is not None
        lines = db.execute(
            select(LedgerJournalLine).where(LedgerJournalLine.entry_id == entry.id)
        ).scalars().all()
        assert len(lines) == 2
        events = db.execute(
            select(ExecutionEvent)
            .where(ExecutionEvent.correlation_id == cid)
            .order_by(ExecutionEvent.occurred_at)
        ).scalars().all()
    assert [e.event_type for e in events] == ["execution.plan", "execution.executed"]
    assert all(e.correlation_id == cid for e in events)
    assert events[0].causation_id is None
    assert events[1].causation_id == cid  # causally linked to the correlation root


def test_execute_is_once_only(world):
    admin = token(world, "slug_a", "admin")
    cid = new_cid("once")
    run_id = decide(admin, "outbox_flush", {}, cid).json()["id"]
    first = httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin), timeout=TIMEOUT)
    assert first.status_code == 200 and first.json()["status"] == "SUCCEEDED"
    second = httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin), timeout=TIMEOUT)
    assert second.status_code == 409, second.text


def test_unknown_intent_is_rejected_before_execution(world):
    admin = token(world, "slug_a", "admin")
    cid = new_cid("bad")
    r = decide(admin, "delete_everything", {}, cid)
    assert r.status_code == 400, r.text
    assert "unknown intent" in r.json()["detail"]


def test_verify_records_outcome_and_correlation(world):
    admin = token(world, "slug_a", "admin")
    cid = new_cid("verify")
    run_id = decide(admin, "outbox_flush", {}, cid).json()["id"]
    httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin), timeout=TIMEOUT)
    r = httpx.post(
        f"{BASE}/api/v1/execution/runs/{run_id}/verify",
        headers=auth(admin),
        params={"outcome": "VERIFIED"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "VERIFYING"
    assert r.json()["decision_json"]["verification_outcome"] == "VERIFIED"
    with session_scope() as db:
        event_types = {
            e.event_type
            for e in db.execute(
                select(ExecutionEvent).where(ExecutionEvent.correlation_id == cid)
            ).scalars()
        }
    assert "execution.verified" in event_types


# --------------------------------------------------------------------------
# event log + outbox
# --------------------------------------------------------------------------
def test_execution_events_are_append_only(world):
    admin = token(world, "slug_a", "admin")
    cid = new_cid("immutable")
    decide(admin, "outbox_flush", {}, cid)
    with session_scope() as db:
        event_id = db.execute(
            select(ExecutionEvent.id).where(ExecutionEvent.correlation_id == cid)
        ).scalar_one()
    import sqlalchemy.exc

    with pytest.raises(sqlalchemy.exc.DatabaseError):
        with session_scope() as db:
            db.execute(text("UPDATE execution_events SET event_type = 'tampered' WHERE id = :i"), {"i": event_id})
    with pytest.raises(sqlalchemy.exc.DatabaseError):
        with session_scope() as db:
            db.execute(text("DELETE FROM execution_events WHERE id = :i"), {"i": event_id})
    # the row is still there, untouched
    with session_scope() as db:
        assert db.execute(
            select(ExecutionEvent.event_type).where(ExecutionEvent.id == event_id)
        ).scalar_one() == "execution.plan"


def test_events_and_runs_are_listed_for_the_owning_tenant(world):
    viewer = token(world, "slug_a", "viewer")
    admin = token(world, "slug_a", "admin")
    cid = new_cid("list")
    run_id = decide(admin, "outbox_flush", {}, cid).json()["id"]

    r = httpx.get(f"{BASE}/api/v1/execution/runs", headers=auth(viewer), timeout=TIMEOUT)
    assert r.status_code == 200
    assert run_id in {x["id"] for x in r.json()}

    r = httpx.get(
        f"{BASE}/api/v1/execution/events", headers=auth(viewer),
        params={"correlation_id": cid}, timeout=TIMEOUT,
    )
    assert r.status_code == 200
    assert {e["correlation_id"] for e in r.json()} == {cid}


def test_outbox_pending_is_listed_then_flushed_by_the_controller(world):
    cid = new_cid("outbox")
    with session_scope() as db:
        outbox = enqueue_outbox(
            db, tenant_id=world["t_a"], correlation_id=cid, destination="valkey", payload={"kind": "test"}
        )
        outbox_id = outbox.id

    admin = token(world, "slug_a", "admin")
    r = httpx.get(f"{BASE}/api/v1/execution/outbox/pending", headers=auth(admin), timeout=TIMEOUT)
    assert r.status_code == 200
    assert outbox_id in {o["id"] for o in r.json()}

    run_id = decide(admin, "outbox_flush", {}, cid).json()["id"]
    ex = httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin), timeout=TIMEOUT)
    assert ex.status_code == 200, ex.text
    r = httpx.get(f"{BASE}/api/v1/execution/outbox/pending", headers=auth(admin), timeout=TIMEOUT)
    assert outbox_id not in {o["id"] for o in r.json()}
    with session_scope() as db:
        row = db.get(OutboxEvent, outbox_id)
        assert row.state == "dispatched"
        assert row.dispatched_at is not None


# --------------------------------------------------------------------------
# approvals: deny-by-default, record-only, no decision path
# --------------------------------------------------------------------------
def test_approval_requests_are_deny_by_default_and_terminal_once(world):
    admin = token(world, "slug_a", "admin")
    viewer = token(world, "slug_a", "viewer")
    cid = new_cid("approval")

    r = httpx.post(
        f"{BASE}/api/v1/approval-requests", headers=auth(admin),
        params={"request_type": "spend", "correlation_id": cid}, timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    request_id = r.json()["id"]
    assert r.json()["status"] == "PENDING"
    assert r.json()["requested_by"] == world["a_admin"]

    r = httpx.get(f"{BASE}/api/v1/approval-requests", headers=auth(viewer), timeout=TIMEOUT)
    assert r.status_code == 200
    assert request_id in {a["id"] for a in r.json()}

    # decisions require authentication (deny-by-default)
    r = httpx.post(f"{BASE}/api/v1/approval-requests/{request_id}/approve", timeout=TIMEOUT)
    assert r.status_code == 401

    # approve once: terminal
    r = httpx.post(
        f"{BASE}/api/v1/approval-requests/{request_id}/approve", headers=auth(admin), timeout=TIMEOUT
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    # a second decision (either way) is rejected, never silently accepted
    for action in ("approve", "deny"):
        r = httpx.post(
            f"{BASE}/api/v1/approval-requests/{request_id}/{action}", headers=auth(admin), timeout=TIMEOUT
        )
        assert r.status_code == 409, r.text
    with session_scope() as db:
        assert db.get(ApprovalRequest, request_id).status == "APPROVED"


# --------------------------------------------------------------------------
# workflows: query-verify-retry via the API
# --------------------------------------------------------------------------
def test_workflow_query_verify_retry_through_api(world):
    admin = token(world, "slug_a", "admin")
    cid = new_cid("wf")
    r = httpx.post(
        f"{BASE}/api/v1/execution/workflows", headers=auth(admin),
        params={"workflow_type": "provider_settlement", "correlation_id": cid}, timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    wf_id = r.json()["id"]
    assert r.json()["status"] == "PENDING"
    assert r.json()["verification_outcome"] == "UNVERIFIED"

    r = httpx.post(
        f"{BASE}/api/v1/execution/workflows/{wf_id}/verify", headers=auth(admin),
        params={"outcome": "VERIFIED"}, timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SUCCEEDED"
    assert r.json()["verification_outcome"] == "VERIFIED"

    # terminal exactly once
    r = httpx.post(
        f"{BASE}/api/v1/execution/workflows/{wf_id}/verify", headers=auth(admin),
        params={"outcome": "VERIFICATION_FAILED"}, timeout=TIMEOUT,
    )
    assert r.status_code == 409, r.text

    r = httpx.get(f"{BASE}/api/v1/execution/workflows", headers=auth(admin), timeout=TIMEOUT)
    assert r.status_code == 200
    assert wf_id in {w["id"] for w in r.json()}


# --------------------------------------------------------------------------
# tenant isolation
# --------------------------------------------------------------------------
def test_cross_tenant_execution_isolation(world):
    admin_a = token(world, "slug_a", "admin")
    admin_b = token(world, "slug_b", "admin")
    cid = new_cid("iso")
    run_id = decide(admin_a, "outbox_flush", {}, cid).json()["id"]

    # B can neither read A's run nor its events nor its approvals
    assert httpx.get(f"{BASE}/api/v1/execution/runs/{run_id}", headers=auth(admin_b), timeout=TIMEOUT).status_code == 404
    assert httpx.get(
        f"{BASE}/api/v1/execution/runs", headers=auth(admin_b), timeout=TIMEOUT
    ).json() == []
    assert httpx.get(
        f"{BASE}/api/v1/execution/events", headers=auth(admin_b), params={"correlation_id": cid}, timeout=TIMEOUT
    ).json() == []
    assert httpx.get(
        f"{BASE}/api/v1/execution/outbox/pending", headers=auth(admin_b), timeout=TIMEOUT
    ).json() == []
    assert httpx.get(
        f"{BASE}/api/v1/approval-requests", headers=auth(admin_b), timeout=TIMEOUT
    ).json() == []
    # and B cannot execute A's run
    r = httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin_b), timeout=TIMEOUT)
    assert r.status_code == 404


# --------------------------------------------------------------------------
# V1A-4: capability registry, policy, SpendGuard budgets, adapters, approvals
# --------------------------------------------------------------------------
def test_capability_registration_is_admin_only_and_deny_by_default(world):
    admin = token(world, "slug_a", "admin")
    viewer = token(world, "slug_a", "viewer")
    op = token(world, "slug_a", "op")
    cap_id = f"itest-cap-{world['suffix']}"

    # write requires TENANT_ADMIN
    for tok in (viewer, op):
        r = httpx.post(
            f"{BASE}/api/v1/capabilities", headers=auth(tok),
            json={"provider_id": "itest", "capability_id": cap_id}, timeout=TIMEOUT,
        )
        assert r.status_code == 403, r.text

    # admin registers it unverified/disabled (the default)
    r = httpx.post(
        f"{BASE}/api/v1/capabilities", headers=auth(admin),
        json={"provider_id": "itest", "capability_id": cap_id}, timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    assert r.json()["verification_state"] == "UNVERIFIED"
    assert r.json()["enabled"] is False

    # reads are allowed for read-only roles
    r = httpx.get(f"{BASE}/api/v1/capabilities", headers=auth(viewer), timeout=TIMEOUT)
    assert r.status_code == 200
    assert cap_id in {c["capability_id"] for c in r.json()}


def test_unverified_capability_denies_adapter_intent(world):
    admin = token(world, "slug_a", "admin")
    cid = new_cid("capdeny")
    payload = {
        "adapter_id": "awin_publisher",
        "capability_id": "awin_publisher_redirect",
        "operation": "publisher_redirect",
    }
    r = decide(admin, "invoke_adapter", payload, cid)
    assert r.status_code == 201, r.text
    body = r.json()
    # the Awin capability is UNVERIFIED -> the guard is DENIED, not UNVERIFIED-usable
    assert body["capability_state"] == "DENIED"
    assert body["status"] == "DENIED"
    # a denied run is not executable
    ex = httpx.post(
        f"{BASE}/api/v1/execution/runs/{body['id']}/execute", headers=auth(admin), timeout=TIMEOUT
    )
    assert ex.status_code == 409, ex.text


def test_verified_capability_still_denied_without_policy_then_allowed_by_policy(world):
    admin = token(world, "slug_a", "admin")
    cap_id = f"itest-verified-{world['suffix']}"
    r = httpx.post(
        f"{BASE}/api/v1/capabilities", headers=auth(admin),
        json={"provider_id": "itest", "capability_id": cap_id,
              "verification_state": "VERIFIED", "enabled": True}, timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text

    payload = {"adapter_id": "awin_publisher", "capability_id": cap_id, "operation": "publisher_redirect"}
    cid = new_cid("capok")
    body = decide(admin, "invoke_adapter", payload, cid).json()
    # capability OK, but no policy grants invoke_adapter -> policy deny-by-default
    assert body["capability_state"] == "ALLOWED"
    assert body["policy_state"] == "DENIED"
    assert body["status"] == "DENIED"

    # grant the policy -> the run now plans
    r = httpx.post(
        f"{BASE}/api/v1/execution-policies", headers=auth(admin),
        json={"intent": "invoke_adapter", "effect": "ALLOW"}, timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    cid2 = new_cid("capok2")
    body2 = decide(admin, "invoke_adapter", payload, cid2).json()
    assert body2["policy_state"] == "ALLOWED"
    assert body2["status"] == "PLANNED"
    # the Awin adapter is still disabled -> execution is refused at the adapter boundary
    ex = httpx.post(
        f"{BASE}/api/v1/execution/runs/{body2['id']}/execute", headers=auth(admin), timeout=TIMEOUT
    )
    assert ex.status_code == 409, ex.text
    assert "adapter" in ex.json()["detail"]


def test_spend_budget_is_admin_only_and_denies_over_budget(world):
    admin = token(world, "slug_a", "admin")
    viewer = token(world, "slug_a", "viewer")
    provider = f"itest-prov-{world['suffix']}"

    r = httpx.post(
        f"{BASE}/api/v1/spend-guard/budgets", headers=auth(viewer),
        json={"currency": "USD", "limit_amount": "10", "provider_id": provider}, timeout=TIMEOUT,
    )
    assert r.status_code == 403, r.text

    r = httpx.post(
        f"{BASE}/api/v1/spend-guard/budgets", headers=auth(admin),
        json={"currency": "USD", "limit_amount": "10", "provider_id": provider}, timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text

    # a provider event that projects over budget denies the run
    cid = new_cid("budget")
    payload = {
        "provider_id": provider, "currency": "USD", "amount": "99",
        "cost_type": "api_call", "occurred_at": "2026-10-01T00:00:00+00:00",
    }
    body = decide(admin, "ingest_provider_event", payload, cid).json()
    assert body["spend_guard_state"] == "DENIED"
    assert body["status"] == "DENIED"


def test_adapters_surface_reports_awin_disabled(world):
    viewer = token(world, "slug_a", "viewer")
    r = httpx.get(f"{BASE}/api/v1/adapters", headers=auth(viewer), timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    awin = {a["adapter_id"]: a for a in r.json()}["awin_publisher"]
    assert awin["enabled"] is False
    assert awin["capability_id"] == "awin_publisher_redirect"


def test_approval_gates_execution_run_and_releases_on_approve(world):
    admin = token(world, "slug_a", "admin")
    # a policy that requires approval for the internal post_journal_entry intent
    r = httpx.post(
        f"{BASE}/api/v1/execution-policies", headers=auth(admin),
        json={"intent": "post_journal_entry", "effect": "ALLOW", "requires_approval": True},
        timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text

    cid = new_cid("apprgate")
    body = decide(admin, "post_journal_entry", post_entry_payload(f"idem-{cid}"), cid).json()
    assert body["approval_state"] == "REQUIRED"
    assert body["status"] == "APPROVAL_REQUIRED"
    run_id = body["id"]

    # executing an approval-parked run is refused
    ex = httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin), timeout=TIMEOUT)
    assert ex.status_code == 409, ex.text

    # the run has a pending approval request linked to it
    with session_scope() as db:
        req = db.execute(
            select(ApprovalRequest).where(ApprovalRequest.run_id == run_id)
        ).scalar_one()
        req_id = req.id
        assert req.status == "PENDING"

    r = httpx.post(
        f"{BASE}/api/v1/approval-requests/{req_id}/approve", headers=auth(admin), timeout=TIMEOUT
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"

    # the run is released to PLANNED and now executes
    r = httpx.get(f"{BASE}/api/v1/execution/runs/{run_id}", headers=auth(admin), timeout=TIMEOUT)
    assert r.json()["status"] == "PLANNED"
    ex = httpx.post(f"{BASE}/api/v1/execution/runs/{run_id}/execute", headers=auth(admin), timeout=TIMEOUT)
    assert ex.status_code == 200, ex.text
    assert ex.json()["status"] == "SUCCEEDED"

    # reset the policy so other tests see the internal default again
    httpx.post(
        f"{BASE}/api/v1/execution-policies", headers=auth(admin),
        json={"intent": "post_journal_entry", "effect": "ALLOW", "requires_approval": False},
        timeout=TIMEOUT,
    )
